# -*- coding: utf-8 -*-
from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

GRUPOS = (
    'product.group_product_manager',
    'purchase.group_purchase_manager',
    'sales_team.group_sale_manager',
    'stock.group_stock_manager',
    'sng_comercial.group_sng_comercial_manager',
)


class ComercialCommon(AccountTestInvoicingCommon):
    """Datos mínimos para los reportes comerciales.

    Trabaja en la compañía de prueba de ``AccountTestInvoicingCommon`` (con su
    plan de cuentas) y con un usuario real, así las reglas multi-compañía de
    los reportes aplican. Corre igual en una base vacía que en una copia de
    producción: reutiliza los atributos que ya tengan uso comercial (solo puede
    haber uno por uso) y crea sus propios valores y productos.

    Los documentos se arman a bajo nivel (movimiento de stock hecho ligado a
    una línea de OC, factura ligada a una línea de OV) para no depender de los
    flujos de aprobación de compras y ventas de cada base.
    """

    @classmethod
    def get_default_groups(cls):
        groups = super().get_default_groups()
        for xmlid in GRUPOS:
            groups |= cls.env.ref(xmlid)
        return groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_company = cls.env['res.company'].create({'name': 'Comercial bodega test'})
        cls.env.user.company_ids |= cls.other_company

        Attribute = cls.env['product.attribute']
        cls.attr = {}
        for rol in ('pilar', 'base', 'volumen'):
            cls.attr[rol] = Attribute.search([('sng_comercial_rol', '=', rol)], limit=1) or Attribute.create({
                'name': 'Comercial test %s' % rol,
                'create_variant': 'no_variant',
                'sng_comercial_rol': rol,
            })
        cls.pilar = cls._valor('pilar', 'PILAR TEST')
        cls.pilar_b = cls._valor('pilar', 'PILAR TEST B')
        cls.base = cls._valor('base', 'BASE TEST')
        cls.vol_5 = cls._valor('volumen', 'Garrafa test 5L')
        cls.vol_400 = cls._valor('volumen', 'Spray test 400ml')

        cls.proveedor = cls.env['res.partner'].create({'name': 'Proveedor comercial test'})
        cls.cliente = cls.env['res.partner'].create({'name': 'Cliente comercial test'})
        cls.Sell = cls.env['sng.comercial.sell.report']
        cls.Inventario = cls.env['sng.comercial.inventario.report']

    @classmethod
    def _valor(cls, rol, nombre):
        return cls.env['product.attribute.value'].create({
            'name': nombre, 'attribute_id': cls.attr[rol].id})

    @classmethod
    def _producto(cls, nombre, codigo, pilar=None, base=None, volumen=None, company=None, **extra):
        company = company or cls.company
        lineas = [
            Command.create({'attribute_id': valor.attribute_id.id, 'value_ids': [Command.set(valor.ids)]})
            for valor in (pilar, base, volumen) if valor
        ]
        template = cls.env['product.template'].with_company(company).create({
            'name': nombre,
            'default_code': codigo,
            'type': 'consu',
            'is_storable': True,
            'company_id': company.id,
            'taxes_id': [Command.clear()],
            'supplier_taxes_id': [Command.clear()],
            'attribute_line_ids': lineas,
            **extra,
        })
        return template.product_variant_id

    @classmethod
    def _stock_location(cls, company):
        return cls.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1).lot_stock_id

    @classmethod
    def _orden_compra(cls, product, qty, company=None, uom=None):
        company = company or cls.company
        return cls.env['purchase.order'].with_company(company).create({
            'partner_id': cls.proveedor.id,
            'company_id': company.id,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_qty': qty,
                'product_uom': (uom or product.uom_po_id).id,
                'price_unit': 1.0,
                'taxes_id': [Command.clear()],
            })],
        })

    @classmethod
    def _recibir(cls, product, qty, fecha, company=None, devolucion=False, uom=None, orden=None):
        """Movimiento hecho ligado a una línea de OC. ``devolucion`` lo invierte."""
        company = company or cls.company
        orden = orden or cls._orden_compra(product, qty, company=company, uom=uom)
        proveedores = cls.env.ref('stock.stock_location_suppliers')
        interna = cls._stock_location(company)
        origen, destino = (interna, proveedores) if devolucion else (proveedores, interna)
        move = cls.env['stock.move'].with_company(company).create({
            'name': product.display_name,
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': (uom or product.uom_id).id,
            'location_id': origen.id,
            'location_dest_id': destino.id,
            'purchase_line_id': orden.order_line[:1].id,
            'company_id': company.id,
        })
        move._action_confirm()
        move.quantity = qty
        move.picked = True
        move._action_done()
        move.date = fields.Datetime.to_datetime('%s 18:00:00' % fecha)
        return move

    @classmethod
    def _facturar(cls, product, qty, fecha, company=None, refund=False, con_ov=True, uom=None, publicar=True):
        """Factura (o nota de crédito) de cliente, ligada a una línea de OV."""
        company = company or cls.company
        Move = cls.env['account.move'].with_company(company)
        linea = {
            'product_id': product.id,
            'quantity': qty,
            'price_unit': 100.0,
            'tax_ids': [Command.clear()],
        }
        if uom:
            linea['product_uom_id'] = uom.id
        if con_ov:
            orden = cls.env['sale.order'].with_company(company).create({
                'partner_id': cls.cliente.id,
                'company_id': company.id,
                'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': qty})],
            })
            linea['sale_line_ids'] = [Command.set(orden.order_line.ids)]
        vals = {
            'move_type': 'out_refund' if refund else 'out_invoice',
            'partner_id': cls.cliente.id,
            'company_id': company.id,
            'invoice_date': fecha,
            'date': fecha,
            'invoice_line_ids': [Command.create(linea)],
        }
        # Facturación electrónica de Costa Rica, si está instalada: sin envío a Hacienda.
        if 'tipo_documento' in Move._fields:
            vals['tipo_documento'] = 'disabled'
        metodo = cls.env.ref('cr_electronic_invoice.PaymentMethods_1', raise_if_not_found=False)
        if metodo and 'payment_methods_id' in Move._fields:
            vals['payment_methods_id'] = metodo.id
        move = Move.create(vals)
        if publicar:
            move.action_post()
        return move

    def _totales(self, productos, dominio=()):
        """(sell in, sell out, litros in, litros out) de los productos dados."""
        self.env.flush_all()
        self.env.invalidate_all()
        grupos = self.Sell._read_group(
            [('product_id', 'in', productos.ids), *dominio], [],
            ['qty_in:sum', 'qty_out:sum', 'litros_in:sum', 'litros_out:sum'])
        return tuple(valor or 0.0 for valor in grupos[0])

    def _inventario(self, product, company=None):
        self.env.flush_all()
        self.env.invalidate_all()
        return self.Inventario.search([
            ('product_id', '=', product.id), ('company_id', '=', (company or self.company).id)])
