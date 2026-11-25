from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestNcControl(TransactionCase):
    """Notas de crédito de cliente: sin inventario desde la factura."""

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
            "name": "Cliente control de notas de crédito",
            "customer_rank": 1,
            "property_account_receivable_id": cls.receivable_account.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Producto despachado",
            "is_storable": True,
            "list_price": 100.0,
            "standard_price": 40.0,
            "invoice_policy": "delivery",
            "property_account_income_id": cls.income_account.id,
        })
        template = cls.product.product_tmpl_id
        if "cabys_product_id" in template._fields:
            template.cabys_product_id = cls.env["cabys.producto"].search([], limit=1)
        if not cls.product.cabys_code and not template._fields["cabys_code"].related:
            template.cabys_code = "8399000000000"
        cls.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": cls.product.id,
            "location_id": cls.warehouse.lot_stock_id.id,
            "inventory_quantity": 50.0,
        }).action_apply_inventory()
        cls.ref_doc = cls.env["reference.document"].search([("code", "=", "01")], limit=1)
        cls.motivo = cls.env["sng.motivo.anulacion"].create({
            "name": "Error de descuento (prueba)",
        })
        cls.return_reason = cls.env["sng.return.reason"].create({
            "name": "Cliente rechaza el pedido",
        })

    def _usuario(self, login, *grupos):
        return self.env["res.users"].create({
            "name": login,
            "login": login,
            "email": "%s@example.com" % login,
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
            "groups_id": [(6, 0, [self.env.ref(grupo).id for grupo in grupos])],
        })

    def setUp(self):
        super().setUp()
        self.order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.warehouse.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 2.0,
                "price_unit": 100.0,
            })],
        })
        self.order.action_confirm()
        self.entrega = self.order.picking_ids
        for move in self.entrega.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self.entrega.with_context(skip_sms=True, skip_backorder=True).button_validate()
        self.invoice = self.order._create_invoices()
        # Sin comprobante electronico: la base de pruebas no firma ni envia.
        self.invoice.tipo_documento = "disabled"
        self.invoice.action_post()

    def _codigo(self, code):
        return self.env["reference.code"].search([("code", "=", code)], limit=1)

    def _asistente(self, code, invoice=None, user=None, **vals):
        invoice = invoice or self.invoice
        return self.env["account.move.reversal"].with_user(user or self.env.user).with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create(dict({
            "journal_id": invoice.journal_id.id,
            "reason": "Prueba",
            "reference_code_id": self._codigo(code).id,
            "reference_document_id": self.ref_doc.id,
        }, **vals))

    def _nota_de_credito(self, code, **vals):
        """NC en borrador creada con el asistente estandar."""
        action = self._asistente(code, **vals).refund_moves()
        credit_note = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit_note.move_type, "out_refund")
        return credit_note

    def _recepcion_historica(self, credit_note):
        """Recepcion como las que creaba la version anterior del modulo."""
        customers = self.env.ref("stock.stock_location_customers")
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.in_type_id.id,
            "partner_id": self.partner.id,
            "origin": credit_note.name,
            "location_id": customers.id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
            "move_ids": [(0, 0, {
                "name": "Return: %s" % self.product.display_name,
                "product_id": self.product.id,
                "product_uom_qty": 2.0,
                "product_uom": self.product.uom_id.id,
                "location_id": customers.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
            })],
        })
        picking.action_confirm()
        credit_note.stock_return_picking_id = picking
        return picking

    # ------------------------------------------------------------------
    # B2: politica por codigo y pregunta del asistente
    # ------------------------------------------------------------------

    def test_politica_de_devolucion_segun_codigo_de_referencia(self):
        self.assertEqual(self._codigo("06").sng_politica_devolucion, "devuelve")
        for code in ("02", "09", "10", "12"):
            self.assertEqual(
                self._codigo(code).sng_politica_devolucion, "no_devuelve", code,
            )
        for code in ("01", "04", "99"):
            self.assertEqual(
                self._codigo(code).sng_politica_devolucion, "preguntar", code,
            )

    def test_asistente_propone_la_respuesta_segun_el_codigo(self):
        self.assertEqual(self._asistente("09").sng_devuelve_mercaderia, "no")
        self.assertEqual(self._asistente("06").sng_devuelve_mercaderia, "si")
        self.assertFalse(self._asistente("01").sng_devuelve_mercaderia)

    def test_cambiar_a_un_codigo_que_pregunta_borra_la_respuesta_propuesta(self):
        wizard = self._asistente("09")
        self.assertEqual(wizard.sng_devuelve_mercaderia, "no")

        wizard.reference_code_id = self._codigo("01")

        self.assertFalse(wizard.sng_devuelve_mercaderia)

    def test_vistas_del_asistente_la_factura_y_el_control_cargan(self):
        asistente = self.env["account.move.reversal"].get_view(view_type="form")["arch"]
        self.assertIn('name="sng_devuelve_mercaderia"', asistente)
        self.assertIn("Anular y refacturar", asistente)
        self.assertIn("Solicitar devolución", asistente)

        factura = self.env["account.move"].get_view(view_type="form")["arch"]
        self.assertIn('name="sng_motivo_anulacion_id"', factura)
        self.assertIn('name="action_sng_crear_factura_sustituta"', factura)
        self.assertNotIn("return_location_required", factura)

        action = self.env.ref(
            "cr_electronic_invoice_credit_limit.action_sng_control_anulaciones"
        )
        lista = self.env["account.move"].get_view(
            self.env.ref(
                "cr_electronic_invoice_credit_limit.view_sng_control_anulaciones_list"
            ).id,
            "list",
        )["arch"]
        self.assertIn('name="sng_estado_control"', lista)
        self.assertEqual(action.res_model, "account.move")
        self.assertTrue(self.env.ref(
            "cr_electronic_invoice_credit_limit.motivo_anulacion_descuento"
        ).active)

    def test_codigo_financiero_crea_nc_aunque_se_responda_que_regresa(self):
        wizard = self._asistente(
            "09",
            sng_devuelve_mercaderia="si",
            sng_return_reason_id=self.return_reason.id,
        )

        action = wizard.refund_moves()

        self.assertEqual(action["res_model"], "account.move")
        self.assertEqual(self.invoice.reversal_move_ids.move_type, "out_refund")
        self.assertFalse(self.env["sng.return"].search([
            ("line_ids.invoice_id", "=", self.invoice.id),
        ]))

    def test_asistente_exige_responder_si_la_mercaderia_regresa(self):
        wizard = self._asistente("01", sng_motivo_anulacion_id=self.motivo.id)

        with self.assertRaisesRegex(UserError, "regresa a bodega"):
            wizard.refund_moves()

        self.assertFalse(self.invoice.reversal_move_ids)

    def test_asistente_no_pregunta_si_la_factura_no_se_ha_despachado(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.warehouse.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "price_unit": 100.0,
            })],
        })
        order.action_confirm()
        order.order_line.product_id.invoice_policy = "order"
        invoice = order._create_invoices()
        invoice.tipo_documento = "disabled"
        invoice.action_post()
        wizard = self._asistente(
            "01", invoice=invoice, sng_motivo_anulacion_id=self.motivo.id,
        )

        action = wizard.refund_moves()

        self.assertFalse(wizard.sng_tiene_entrega)
        self.assertEqual(action["res_model"], "account.move")

    # ------------------------------------------------------------------
    # B1: la NC desde la factura no mueve inventario
    # ------------------------------------------------------------------

    def test_nc_de_anulacion_sobre_factura_despachada_no_crea_recepcion(self):
        credit_note = self._nota_de_credito(
            "01",
            sng_devuelve_mercaderia="no",
            sng_motivo_anulacion_id=self.motivo.id,
        )

        credit_note.action_post()

        self.assertEqual(credit_note.state, "posted")
        self.assertEqual(credit_note.sng_motivo_anulacion_id, self.motivo)
        self.assertEqual(credit_note.amount_total, self.invoice.amount_total)
        self.assertFalse(credit_note.stock_return_picking_id)
        self.assertFalse(credit_note.return_location_id)
        self.assertEqual(self.order.picking_ids, self.entrega)
        self.assertFalse(self.env["stock.picking"].search([
            ("origin", "=", credit_note.name),
        ]))
        self.assertEqual(self.order.order_line.qty_delivered, 2.0)

    def test_nc_financiera_sobre_factura_despachada_no_crea_recepcion(self):
        credit_note = self._nota_de_credito("09")

        credit_note.action_post()

        self.assertEqual(credit_note.state, "posted")
        self.assertFalse(credit_note.stock_return_picking_id)
        self.assertEqual(self.order.picking_ids, self.entrega)

    def test_nc_de_anulacion_exige_motivo_al_confirmar(self):
        credit_note = self._nota_de_credito("01", sng_devuelve_mercaderia="no")

        with self.assertRaisesRegex(UserError, "motivo de anulación"):
            credit_note.action_post()

    def test_nc_por_devolucion_hecha_a_mano_no_se_puede_confirmar(self):
        credit_note = self.invoice._reverse_moves([{
            "invoice_id": self.invoice.id,
            "tipo_documento": "disabled",
            "reference_code_id": self._codigo("06").id,
            "reference_document_id": self.ref_doc.id,
        }])

        with self.assertRaisesRegex(UserError, "Devoluciones"):
            credit_note.action_post()

    def test_nc_generada_por_devoluciones_se_confirma(self):
        customer_return = self.env["sng.return"]._crear_desde_factura(
            self.invoice, self.return_reason,
        )
        customer_return._confirm_with_warehouse(self.warehouse)
        for move in customer_return.picking_ids.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        customer_return.picking_ids.with_context(
            skip_sms=True, skip_backorder=True,
        ).button_validate()
        customer_return.invalidate_recordset(["receipt_complete", "receipt_state"])
        action = customer_return.action_generate_credit_note()
        credit_note = self.env["account.move"].browse(action["res_id"])
        credit_note.tipo_documento = "disabled"

        credit_note.action_post()

        self.assertEqual(credit_note.state, "posted")
        self.assertEqual(credit_note.reference_code_id.code, "06")
        self.assertEqual(credit_note.stock_return_picking_id, customer_return.picking_id)
        self.assertEqual(credit_note.sng_estado_control, "ok")

    # ------------------------------------------------------------------
    # B2: si la mercaderia regresa, el camino es Devoluciones
    # ------------------------------------------------------------------

    def test_respuesta_si_abre_una_devolucion_y_no_crea_nota_de_credito(self):
        wizard = self._asistente(
            "01",
            sng_devuelve_mercaderia="si",
            sng_return_reason_id=self.return_reason.id,
        )

        action = wizard.refund_moves()

        self.assertEqual(action["res_model"], "sng.return")
        customer_return = self.env["sng.return"].browse(action["res_id"])
        self.assertEqual(customer_return.state, "draft")
        self.assertEqual(customer_return.reason_id, self.return_reason)
        self.assertEqual(customer_return.line_ids.invoice_id, self.invoice)
        self.assertEqual(customer_return.line_ids.quantity, 2.0)
        self.assertFalse(self.invoice.reversal_move_ids)

    def test_respuesta_si_exige_motivo_de_devolucion(self):
        wizard = self._asistente("06")

        with self.assertRaisesRegex(UserError, "motivo de la devolución"):
            wizard.refund_moves()

    def test_respuesta_si_sin_permiso_de_devoluciones_da_mensaje_claro(self):
        usuario = self.env["res.users"].create({
            "name": "Facturación sin Devoluciones",
            "login": "facturacion-sin-devoluciones",
            "email": "facturacion-sin-devoluciones@example.com",
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
            "groups_id": [(6, 0, [self.env.ref("account.group_account_invoice").id])],
        })
        wizard = self._asistente(
            "06", user=usuario, sng_return_reason_id=self.return_reason.id,
        )

        with self.assertRaisesRegex(AccessError, "Usuario de Devoluciones"):
            wizard.refund_moves()

    # ------------------------------------------------------------------
    # B3: anular y refacturar
    # ------------------------------------------------------------------

    def test_anular_y_refacturar_deja_nc_confirmada_y_factura_nueva_en_borrador(self):
        wizard = self._asistente("99", sng_motivo_anulacion_id=self.motivo.id)

        action = wizard.modify_moves()

        credit_note = self.invoice.reversal_move_ids
        self.assertEqual(len(credit_note), 1)
        self.assertEqual(credit_note.state, "posted")
        self.assertEqual(credit_note.reference_code_id.code, "01")
        self.assertEqual(credit_note.sng_motivo_anulacion_id, self.motivo)
        # Paso por action_post de la factura electronica: tiene consecutivo.
        self.assertTrue(credit_note.sequence)
        # Aplicada a la factura original por la confirmacion estandar.
        self.assertEqual(self.invoice.amount_residual, 0.0)
        self.assertEqual(credit_note.amount_residual, 0.0)

        nueva = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(action["res_model"], "account.move")
        self.assertEqual(nueva.move_type, "out_invoice")
        self.assertEqual(nueva.state, "draft")
        self.assertEqual(nueva.sng_factura_anulada_id, self.invoice)
        self.assertEqual(credit_note.sng_factura_sustituta_id, nueva)
        self.assertEqual(nueva.invoice_line_ids.sale_line_ids, self.order.order_line)
        self.assertEqual(nueva.invoice_line_ids.quantity, 2.0)
        self.assertFalse(nueva.number_electronic)
        self.assertFalse(nueva.sequence)
        self.assertFalse(nueva.state_tributacion)

        # La mercaderia no se mueve y la orden sigue facturada.
        self.assertEqual(self.order.picking_ids, self.entrega)
        self.assertFalse(credit_note.stock_return_picking_id)
        self.assertEqual(self.order.order_line.qty_invoiced, 2.0)
        self.assertEqual(self.order.order_line.qty_delivered, 2.0)
        self.assertEqual(self.order.invoice_status, "invoiced")

    def test_anular_y_refacturar_crea_la_sustituta_antes_de_confirmar_la_nc(self):
        # Confirmar la NC la envia a Hacienda: todo lo que puede fallar va antes.
        Move = type(self.env["account.move"])
        action_post = Move.action_post
        tenia_sustituta = []

        def espia(records):
            tenia_sustituta.extend(
                bool(move.sng_factura_sustituta_id)
                for move in records if move.move_type == "out_refund"
            )
            return action_post(records)

        wizard = self._asistente("01", sng_motivo_anulacion_id=self.motivo.id)
        with patch.object(Move, "action_post", espia):
            wizard.modify_moves()

        self.assertEqual(tenia_sustituta, [True])

    def test_anular_y_refacturar_exige_motivo(self):
        wizard = self._asistente("01")

        with self.assertRaisesRegex(UserError, "motivo de anulación"):
            wizard.modify_moves()

        self.assertFalse(self.invoice.reversal_move_ids)

    def test_factura_sustituta_se_puede_crear_desde_la_nc_confirmada(self):
        credit_note = self._nota_de_credito(
            "01",
            sng_devuelve_mercaderia="no",
            sng_motivo_anulacion_id=self.motivo.id,
        )
        credit_note.action_post()
        self.assertTrue(credit_note.sng_puede_crear_sustituta)

        action = credit_note.action_sng_crear_factura_sustituta()

        nueva = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(nueva.state, "draft")
        self.assertEqual(nueva.sng_factura_anulada_id, self.invoice)
        self.assertEqual(credit_note.sng_factura_sustituta_id, nueva)
        self.assertEqual(nueva.invoice_line_ids.sale_line_ids, self.order.order_line)
        self.assertFalse(credit_note.sng_puede_crear_sustituta)
        with self.assertRaisesRegex(UserError, "ya tiene una factura sustituta"):
            credit_note.action_sng_crear_factura_sustituta()

    # ------------------------------------------------------------------
    # B4: estado de control
    # ------------------------------------------------------------------

    def test_estado_de_control_marca_anulacion_sin_refactura(self):
        wizard = self._asistente("01", sng_motivo_anulacion_id=self.motivo.id)
        action = wizard.modify_moves()
        credit_note = self.invoice.reversal_move_ids
        nueva = self.env["account.move"].browse(action["res_id"])

        self.assertEqual(credit_note.sng_estado_control, "sin_refactura")

        nueva.tipo_documento = "disabled"
        nueva.action_post()

        self.assertEqual(credit_note.sng_estado_control, "ok")
        self.assertFalse(self.invoice.sng_estado_control)

    def test_estado_de_control_no_pide_refactura_si_el_motivo_no_la_requiere(self):
        self.motivo.requiere_refactura = False
        credit_note = self._nota_de_credito(
            "01",
            sng_devuelve_mercaderia="no",
            sng_motivo_anulacion_id=self.motivo.id,
        )

        credit_note.action_post()

        self.assertEqual(credit_note.sng_estado_control, "ok")

    def test_estado_de_control_no_marca_anulaciones_anteriores_sin_motivo(self):
        credit_note = self._nota_de_credito(
            "01",
            sng_devuelve_mercaderia="no",
            sng_motivo_anulacion_id=self.motivo.id,
        )
        credit_note.action_post()
        self.assertEqual(credit_note.sng_estado_control, "sin_refactura")

        # Las anulaciones anteriores al control no tienen motivo.
        credit_note.sng_motivo_anulacion_id = False

        self.assertEqual(credit_note.sng_estado_control, "ok")

    def test_recepcion_de_la_nc_tiene_indice_para_el_recalculo_del_control(self):
        self.assertTrue(
            self.env["account.move"]._fields["stock_return_picking_id"].index
        )

    # ------------------------------------------------------------------
    # B1: recepciones historicas creadas por la version anterior
    # ------------------------------------------------------------------

    def test_pasar_a_borrador_nc_historica_cancela_su_recepcion_pendiente(self):
        credit_note = self._nota_de_credito(
            "01",
            sng_devuelve_mercaderia="no",
            sng_motivo_anulacion_id=self.motivo.id,
        )
        credit_note.action_post()
        picking = self._recepcion_historica(credit_note)
        self.assertEqual(credit_note.sng_estado_control, "recepcion_pendiente")

        credit_note.button_draft()

        self.assertEqual(credit_note.state, "draft")
        self.assertEqual(picking.state, "cancel")

    def test_nc_historica_con_recepcion_validada_no_vuelve_a_borrador(self):
        credit_note = self._nota_de_credito(
            "01",
            sng_devuelve_mercaderia="no",
            sng_motivo_anulacion_id=self.motivo.id,
        )
        credit_note.action_post()
        picking = self._recepcion_historica(credit_note)
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.with_context(skip_sms=True, skip_backorder=True).button_validate()

        with self.assertRaisesRegex(UserError, "recepción validada"):
            credit_note.button_draft()

        self.assertEqual(credit_note.state, "posted")

    def test_nc_historica_con_recepcion_validada_y_devuelta_vuelve_a_borrador(self):
        credit_note = self._nota_de_credito(
            "01",
            sng_devuelve_mercaderia="no",
            sng_motivo_anulacion_id=self.motivo.id,
        )
        credit_note.action_post()
        picking = self._recepcion_historica(credit_note)
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.with_context(skip_sms=True, skip_backorder=True).button_validate()
        # Bodega devuelve la recepcion completa: la mercaderia vuelve a salir.
        devolucion = self.env["stock.return.picking"].create({"picking_id": picking.id})
        for line in devolucion.product_return_moves:
            line.quantity = line.move_id.quantity
        salida = devolucion._create_return()
        for move in salida.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        salida.with_context(skip_sms=True, skip_backorder=True).button_validate()
        self.assertEqual(salida.state, "done")

        credit_note.button_draft()

        self.assertEqual(credit_note.state, "draft")

    def test_duplicar_nc_no_copia_la_recepcion(self):
        credit_note = self._nota_de_credito(
            "01",
            sng_devuelve_mercaderia="no",
            sng_motivo_anulacion_id=self.motivo.id,
        )
        self._recepcion_historica(credit_note)
        credit_note.return_location_id = self.warehouse.lot_stock_id

        copia = credit_note.copy()

        self.assertFalse(copia.stock_return_picking_id)
        self.assertFalse(copia.return_location_id)

    # ------------------------------------------------------------------
    # Solo usuarios autorizados crean notas de crédito de cliente
    # ------------------------------------------------------------------

    GRUPO_NC = "cr_electronic_invoice_credit_limit.group_sng_crear_nota_credito"

    def test_usuario_sin_autorizacion_no_crea_nc_desde_la_factura(self):
        usuario = self._usuario("facturacion-sin-nc", "account.group_account_invoice")
        wizard = self._asistente(
            "09", user=usuario, sng_motivo_anulacion_id=self.motivo.id,
        )

        with self.assertRaisesRegex(AccessError, "notas de crédito de cliente"):
            wizard.refund_moves()

        self.assertFalse(self.invoice.reversal_move_ids)

    def test_usuario_sin_autorizacion_no_crea_nc_directa(self):
        usuario = self._usuario("facturacion-sin-nc", "account.group_account_invoice")

        with self.assertRaisesRegex(AccessError, "notas de crédito de cliente"):
            self.env["account.move"].with_user(usuario).create({
                "move_type": "out_refund",
                "partner_id": self.partner.id,
            })
        with self.assertRaisesRegex(AccessError, "notas de crédito de cliente"):
            self.env["account.move"].with_user(usuario).with_context(
                default_move_type="out_refund",
            ).create({"partner_id": self.partner.id})

    def test_usuario_sin_autorizacion_no_convierte_una_factura_en_nc(self):
        usuario = self._usuario("facturacion-sin-nc", "account.group_account_invoice")
        borrador = self.env["account.move"].with_user(usuario).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
        })

        with self.assertRaisesRegex(AccessError, "notas de crédito de cliente"):
            borrador.move_type = "out_refund"

    def test_usuario_autorizado_crea_nc_desde_la_factura(self):
        usuario = self._usuario(
            "facturacion-con-nc", "account.group_account_invoice", self.GRUPO_NC,
        )
        wizard = self._asistente("09", user=usuario)

        action = wizard.refund_moves()

        credit_note = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit_note.move_type, "out_refund")
        self.assertEqual(credit_note.create_uid, usuario)

    def test_usuario_sin_autorizacion_si_puede_solicitar_la_devolucion(self):
        usuario = self._usuario(
            "facturacion-sin-nc",
            "account.group_account_invoice", "sng_return.group_sng_return_user",
        )
        wizard = self._asistente(
            "06", user=usuario, sng_return_reason_id=self.return_reason.id,
        )

        action = wizard.refund_moves()

        self.assertEqual(action["res_model"], "sng.return")

    def test_regla_de_registro_bloquea_crear_nc_solo_a_no_autorizados(self):
        sin_permiso = self._usuario("facturacion-sin-nc", "account.group_account_invoice")
        con_permiso = self._usuario(
            "facturacion-con-nc", "account.group_account_invoice", self.GRUPO_NC,
        )
        Rule = self.env["ir.rule"]
        restriccion = ("move_type", "!=", "out_refund")

        self.assertIn(
            restriccion,
            Rule.with_user(sin_permiso)._compute_domain("account.move", "create"),
        )
        self.assertNotIn(
            restriccion,
            Rule.with_user(con_permiso)._compute_domain("account.move", "create") or [],
        )
        # Leer y editar notas de crédito existentes no cambia.
        self.assertNotIn(
            restriccion,
            Rule.with_user(sin_permiso)._compute_domain("account.move", "read") or [],
        )

    def test_boton_nota_de_credito_se_oculta_a_quien_no_puede_crearla(self):
        factura = self.env["account.move"].get_view(view_type="form")["arch"]
        self.assertIn("sng_puede_crear_nc", factura)
        sin_permiso = self._usuario("facturacion-sin-nc", "account.group_account_invoice")
        con_permiso = self._usuario(
            "facturacion-con-nc", "account.group_account_invoice", self.GRUPO_NC,
        )

        self.assertFalse(self.invoice.with_user(sin_permiso).sng_puede_crear_nc)
        self.assertTrue(self.invoice.with_user(con_permiso).sng_puede_crear_nc)
        self.assertTrue(self.env.ref("base.user_admin").has_group(self.GRUPO_NC))
