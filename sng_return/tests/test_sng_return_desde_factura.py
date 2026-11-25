from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestSngReturnDesdeFactura(TransactionCase):
    """Devolucion nacida de la factura y recepcion por el proceso estandar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.write({
            "groups_id": [(4, cls.env.ref("sng_return.group_sng_return_supervisor").id)]
        })
        cls.company.payment_method_default_id = cls.env.ref(
            "cr_electronic_invoice.PaymentMethods_1"
        )
        cls.income_account = cls.env["account.account"].create({
            "name": "Ingresos de prueba",
            "code": "TSTINC",
            "account_type": "income",
            "company_ids": [(6, 0, cls.company.ids)],
        })
        cls.receivable_account = cls.env["account.account"].create({
            "name": "Cuentas por cobrar de prueba",
            "code": "TSTREC",
            "account_type": "asset_receivable",
            "reconcile": True,
            "company_ids": [(6, 0, cls.company.ids)],
        })
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)],
            limit=1,
        )
        cls.partner = cls.env["res.partner"].create({
            "name": "Cliente devolución desde factura",
            "customer_rank": 1,
            "property_account_receivable_id": cls.receivable_account.id,
        })
        cls.product = cls._crear_producto("Producto retornable A")
        cls.product_b = cls._crear_producto("Producto retornable B")
        cls.product_order = cls._crear_producto(
            "Producto facturado al ordenar", invoice_policy="order"
        )
        cls.reason = cls.env["sng.return.reason"].create({
            "name": "Producto no requerido",
        })

    @classmethod
    def _crear_producto(cls, name, invoice_policy="delivery"):
        product = cls.env["product.product"].create({
            "name": name,
            "is_storable": True,
            "list_price": 100.0,
            "standard_price": 40.0,
            # En produccion todo lo almacenable se factura por lo entregado.
            "invoice_policy": invoice_policy,
            "property_account_income_id": cls.income_account.id,
        })
        template = product.product_tmpl_id
        if "cabys_product_id" in template._fields:
            template.cabys_product_id = cls.env["cabys.producto"].search([], limit=1)
        if not product.cabys_code and not template._fields["cabys_code"].related:
            template.cabys_code = "8399000000000"
        cls.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": product.id,
            "location_id": cls.warehouse.lot_stock_id.id,
            "inventory_quantity": 50.0,
        }).action_apply_inventory()
        return product

    def _vender(self, lineas):
        """Orden confirmada con las lineas [(producto, cantidad)]."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.warehouse.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "product_uom_qty": qty,
                "price_unit": 100.0,
            }) for product, qty in lineas],
        })
        order.action_confirm()
        return order

    def _entregar(self, picking, cantidades=None):
        """Valida la entrega; ``cantidades`` {producto: qty} para parciales."""
        for move in picking.move_ids:
            qty = move.product_uom_qty
            if cantidades is not None:
                qty = cantidades.get(move.product_id, 0.0)
            move.quantity = qty
            move.picked = True
        picking.with_context(skip_sms=True, skip_backorder=True).button_validate()
        self.assertEqual(picking.state, "done")

    def _facturar(self, order):
        invoice = order._create_invoices()
        # Sin comprobante electronico: la base de pruebas no firma ni envia.
        invoice.tipo_documento = "disabled"
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        return invoice

    def _venta_entregada_y_facturada(self, lineas):
        order = self._vender(lineas)
        self._entregar(order.picking_ids)
        return order, self._facturar(order)

    def _recibir(self, pickings):
        for picking in pickings:
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            picking.with_context(skip_sms=True, skip_backorder=True).button_validate()
            self.assertEqual(picking.state, "done")

    # ------------------------------------------------------------------
    # A1: la devolucion nace de la factura
    # ------------------------------------------------------------------

    def test_crear_desde_factura_deja_borrador_con_lineas_de_la_factura(self):
        order, invoice = self._venta_entregada_y_facturada([
            (self.product, 2.0), (self.product_b, 3.0),
        ])

        customer_return = self.env["sng.return"]._crear_desde_factura(
            invoice, self.reason, notas="Cliente rechaza el pedido",
        )

        self.assertEqual(customer_return.state, "draft")
        self.assertEqual(customer_return.partner_id, self.partner)
        self.assertEqual(customer_return.company_id, invoice.company_id)
        self.assertEqual(customer_return.reason_id, self.reason)
        self.assertEqual(customer_return.notes, "Cliente rechaza el pedido")
        self.assertEqual(
            {line.product_id: line.quantity for line in customer_return.line_ids},
            {self.product: 2.0, self.product_b: 3.0},
        )
        self.assertEqual(customer_return.line_ids.invoice_id, invoice)
        self.assertFalse(customer_return.picking_ids)

    def test_crear_desde_factura_solo_incluye_productos_almacenables(self):
        consumible = self.env["product.product"].create({
            "name": "Consumible sin inventario",
            "type": "consu",
            "is_storable": False,
            "list_price": 10.0,
            "invoice_policy": "order",
            "property_account_income_id": self.income_account.id,
        })
        template = consumible.product_tmpl_id
        if "cabys_product_id" in template._fields:
            template.cabys_product_id = self.env["cabys.producto"].search([], limit=1)
        order, invoice = self._venta_entregada_y_facturada([
            (self.product, 2.0), (consumible, 1.0),
        ])

        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)

        self.assertEqual(customer_return.line_ids.product_id, self.product)

    def test_crear_desde_factura_suma_producto_repetido(self):
        order, invoice = self._venta_entregada_y_facturada([
            (self.product, 2.0), (self.product, 1.0),
        ])

        customer_return = self.env["sng.return"]._crear_desde_factura(
            invoice, self.reason,
        )

        self.assertEqual(len(customer_return.line_ids), 1)
        self.assertEqual(customer_return.line_ids.quantity, 3.0)

    def test_crear_desde_factura_no_exige_gerente_para_fijar_la_factura(self):
        order, invoice = self._venta_entregada_y_facturada([(self.product, 2.0)])
        usuario = self.env["res.users"].create({
            "name": "Facturación sin gerencia de devoluciones",
            "login": "facturacion-devoluciones",
            "email": "facturacion-devoluciones@example.com",
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
            "groups_id": [(6, 0, [
                self.env.ref("account.group_account_invoice").id,
                self.env.ref("sng_return.group_sng_return_user").id,
            ])],
        })

        customer_return = self.env["sng.return"].with_user(usuario)._crear_desde_factura(
            invoice.with_user(usuario), self.reason,
        )

        self.assertEqual(customer_return.user_id, usuario)
        self.assertEqual(customer_return.line_ids.invoice_id, invoice)

    def test_crear_desde_factura_descuenta_lo_ya_devuelto(self):
        order, invoice = self._venta_entregada_y_facturada([(self.product, 2.0)])
        primera = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)
        primera.line_ids.quantity = 1.5
        primera._confirm_with_warehouse(self.warehouse)

        segunda = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)

        self.assertEqual(segunda.line_ids.quantity, 0.5)

    def test_crear_desde_factura_sin_nada_por_devolver_da_error(self):
        order, invoice = self._venta_entregada_y_facturada([(self.product, 2.0)])
        self.env["sng.return"]._crear_desde_factura(
            invoice, self.reason,
        )._confirm_with_warehouse(self.warehouse)

        with self.assertRaisesRegex(UserError, "no queda mercadería por devolver"):
            self.env["sng.return"]._crear_desde_factura(invoice, self.reason)

    def test_crear_desde_factura_rechaza_factura_sin_confirmar(self):
        order = self._vender([(self.product, 2.0)])
        self._entregar(order.picking_ids)
        borrador = order._create_invoices()

        with self.assertRaisesRegex(UserError, "factura de cliente confirmada"):
            self.env["sng.return"]._crear_desde_factura(borrador, self.reason)

    # ------------------------------------------------------------------
    # A2: recepcion por el asistente estandar de devolucion
    # ------------------------------------------------------------------

    def test_confirmar_con_entrega_crea_devolucion_ligada_a_la_entrega(self):
        order, invoice = self._venta_entregada_y_facturada([(self.product, 2.0)])
        entrega = order.picking_ids
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)
        customer_return.line_ids.quantity = 1.0

        customer_return._confirm_with_warehouse(self.warehouse)

        recepcion = customer_return.picking_id
        self.assertEqual(customer_return.state, "confirmed")
        self.assertEqual(customer_return.picking_ids, recepcion)
        self.assertEqual(recepcion.sng_return_id, customer_return)
        self.assertEqual(recepcion.return_id, entrega)
        self.assertEqual(recepcion.picking_type_id, self.warehouse.in_type_id)
        self.assertEqual(recepcion.location_dest_id, customer_return.location_dest_id)
        move = recepcion.move_ids
        self.assertEqual(move.origin_returned_move_id, entrega.move_ids)
        self.assertEqual(move.sale_line_id, order.order_line)
        self.assertTrue(move.to_refund)
        self.assertEqual(move.product_uom_qty, 1.0)
        self.assertEqual(move.location_dest_id, customer_return.location_dest_id)
        self.assertEqual(customer_return.receipt_state, "pending")
        # Nada entra a inventario hasta que bodega valida.
        self.assertEqual(order.order_line.qty_delivered, 2.0)

    def test_no_se_cambia_la_factura_de_una_linea_con_recepcion_ligada_a_la_entrega(self):
        order, invoice = self._venta_entregada_y_facturada([(self.product, 2.0)])
        otra_orden, otra_factura = self._venta_entregada_y_facturada([(self.product, 2.0)])
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)
        customer_return._confirm_with_warehouse(self.warehouse)

        with self.assertRaisesRegex(UserError, "ligada a la entrega"):
            customer_return.line_ids.invoice_id = otra_factura

        # Cancelada la recepcion, la factura se puede cambiar como siempre.
        customer_return.picking_ids.action_cancel()
        customer_return.line_ids.invoice_id = otra_factura
        self.assertEqual(customer_return.line_ids.invoice_id, otra_factura)

    def test_validar_la_recepcion_baja_lo_entregado_de_la_orden(self):
        order, invoice = self._venta_entregada_y_facturada([(self.product, 2.0)])
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)
        customer_return.line_ids.quantity = 1.0
        customer_return._confirm_with_warehouse(self.warehouse)

        self._recibir(customer_return.picking_ids)
        customer_return.invalidate_recordset(["receipt_complete", "receipt_state"])

        self.assertEqual(order.order_line.qty_delivered, 1.0)
        self.assertTrue(customer_return.receipt_complete)
        self.assertEqual(customer_return.receipt_state, "done")

    def test_devolucion_va_al_almacen_elegido_aunque_no_sea_el_de_la_entrega(self):
        otro_almacen = self.env["stock.warehouse"].create({
            "name": "Almacén de desecho de prueba",
            "code": "TDSH",
            "company_id": self.company.id,
        })
        order, invoice = self._venta_entregada_y_facturada([(self.product, 2.0)])
        entrega = order.picking_ids
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)

        customer_return._confirm_with_warehouse(otro_almacen)

        recepcion = customer_return.picking_id
        destino = customer_return._get_return_destination_location(otro_almacen)
        self.assertEqual(recepcion.picking_type_id, otro_almacen.in_type_id)
        self.assertEqual(recepcion.location_dest_id, destino)
        self.assertEqual(recepcion.move_ids.location_dest_id, destino)
        self.assertEqual(recepcion.return_id, entrega)
        self._recibir(recepcion)
        self.assertEqual(recepcion.move_line_ids.location_dest_id, destino)

    def test_devolucion_mayor_a_lo_entregado_da_error_y_no_crea_recepcion(self):
        # Facturado al ordenar: se factura 2 con solo 1 entregada.
        order = self._vender([(self.product_order, 2.0)])
        self._entregar(order.picking_ids, {self.product_order: 1.0})
        invoice = self._facturar(order)
        customer_return = self.env["sng.return"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "reason_id": self.reason.id,
            "line_ids": [(0, 0, {
                "product_id": self.product_order.id,
                "quantity": 2.0,
                "invoice_id": invoice.id,
            })],
        })

        with self.assertRaisesRegex(UserError, "excede lo entregado"):
            customer_return._confirm_with_warehouse(self.warehouse)

        self.assertFalse(customer_return.picking_ids)
        self.assertEqual(customer_return.state, "draft")

    def test_devolucion_se_reparte_entre_las_entregas_de_la_orden(self):
        order = self._vender([(self.product_order, 3.0)])
        primera = order.picking_ids
        primera.move_ids.quantity = 2.0
        primera.move_ids.picked = True
        primera.with_context(skip_sms=True, cancel_backorder=False)._action_done()
        segunda = order.picking_ids - primera
        self.assertTrue(segunda, "La entrega parcial debe dejar una entrega pendiente.")
        self._entregar(segunda)
        invoice = self._facturar(order)
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)

        customer_return._confirm_with_warehouse(self.warehouse)

        recepciones = customer_return.picking_ids
        self.assertEqual(recepciones.return_id, primera | segunda)
        self.assertEqual(
            {picking.return_id: picking.move_ids.product_uom_qty for picking in recepciones},
            {primera: 2.0, segunda: 1.0},
        )
        self.assertIn(customer_return.picking_id, recepciones)
        self._recibir(recepciones)
        customer_return.invalidate_recordset(["receipt_complete", "receipt_state"])
        self.assertTrue(customer_return.receipt_complete)
        self.assertEqual(order.order_line.qty_delivered, 0.0)

    def test_linea_sin_entrega_hecha_sigue_con_la_recepcion_de_siempre(self):
        order = self._vender([(self.product_order, 2.0)])
        invoice = self._facturar(order)
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)

        customer_return._confirm_with_warehouse(self.warehouse)

        recepcion = customer_return.picking_id
        self.assertFalse(recepcion.return_id)
        self.assertFalse(recepcion.move_ids.origin_returned_move_id)
        self.assertEqual(recepcion.location_id, self.partner.property_stock_customer)
        self.assertEqual(recepcion.move_ids.product_uom_qty, 2.0)

    # ------------------------------------------------------------------
    # A3: la nota de credito queda ligada a la orden
    # ------------------------------------------------------------------

    def test_nota_de_credito_de_recepcion_ligada_lleva_la_linea_de_venta(self):
        order, invoice = self._venta_entregada_y_facturada([(self.product, 2.0)])
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)
        customer_return.line_ids.quantity = 1.0
        customer_return._confirm_with_warehouse(self.warehouse)
        self._recibir(customer_return.picking_ids)
        customer_return.invalidate_recordset(["receipt_complete", "receipt_state"])

        action = customer_return.action_generate_credit_note()

        credit_note = self.env["account.move"].browse(action["res_id"])
        linea = credit_note.invoice_line_ids
        self.assertEqual(linea.sale_line_ids, order.order_line)
        self.assertEqual(linea.quantity, 1.0)
        self.assertEqual(credit_note.reversed_entry_id, invoice)
        # Entregado y facturado bajan a la vez: la orden queda cuadrada.
        self.assertEqual(order.order_line.qty_delivered, 1.0)
        self.assertEqual(order.order_line.qty_invoiced, 1.0)
        self.assertEqual(order.order_line.qty_to_invoice, 0.0)
        # Estado estandar de Odoo tras devolver parte: nada pendiente de facturar.
        self.assertEqual(order.invoice_status, "no")

    def test_nota_de_credito_separa_la_cantidad_por_linea_de_venta(self):
        order, invoice = self._venta_entregada_y_facturada([
            (self.product, 2.0), (self.product, 1.0),
        ])
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)
        customer_return._confirm_with_warehouse(self.warehouse)
        self._recibir(customer_return.picking_ids)
        customer_return.invalidate_recordset(["receipt_complete", "receipt_state"])

        action = customer_return.action_generate_credit_note()

        credit_note = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(
            {
                linea.sale_line_ids: linea.quantity
                for linea in credit_note.invoice_line_ids
            },
            {order.order_line[0]: 2.0, order.order_line[1]: 1.0},
        )
        self.assertEqual(order.order_line.mapped("qty_invoiced"), [0.0, 0.0])
        self.assertEqual(order.order_line.mapped("qty_delivered"), [0.0, 0.0])

    def test_nota_de_credito_de_recepcion_sin_ligar_no_toca_la_orden(self):
        order = self._vender([(self.product_order, 2.0)])
        invoice = self._facturar(order)
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)
        customer_return._confirm_with_warehouse(self.warehouse)
        self._recibir(customer_return.picking_ids)
        customer_return.invalidate_recordset(["receipt_complete", "receipt_state"])

        action = customer_return.action_generate_credit_note()

        credit_note = self.env["account.move"].browse(action["res_id"])
        self.assertFalse(credit_note.invoice_line_ids.sale_line_ids)
        self.assertEqual(order.order_line.qty_invoiced, 2.0)

    def test_disponible_por_cliente_no_descuenta_dos_veces_la_nc_ligada(self):
        order, invoice = self._venta_entregada_y_facturada([(self.product, 2.0)])
        customer_return = self.env["sng.return"]._crear_desde_factura(invoice, self.reason)
        customer_return.line_ids.quantity = 1.0
        customer_return._confirm_with_warehouse(self.warehouse)
        self._recibir(customer_return.picking_ids)
        customer_return.invalidate_recordset(["receipt_complete", "receipt_state"])
        customer_return.action_generate_credit_note()
        # Cada paso es una peticion distinta en la interfaz: se vacian los
        # calculos pendientes como al cerrar la peticion.
        self.env.flush_all()

        # Devolucion nueva todavia sin factura: el disponible sale del total
        # facturado al cliente (2) menos lo devuelto (1).
        nueva = self.env["sng.return"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "reason_id": self.reason.id,
            "line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1.0,
            })],
        })

        self.assertEqual(nueva.line_ids.invoiced_sale_qty, 2.0)
        self.assertEqual(nueva.line_ids.previous_return_qty, 1.0)
        self.assertEqual(nueva.line_ids.available_return_qty, 1.0)
