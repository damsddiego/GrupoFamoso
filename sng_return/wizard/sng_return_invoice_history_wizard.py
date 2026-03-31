from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SngReturnInvoiceHistoryWizard(models.TransientModel):
    _name = "sng.return.invoice.history.wizard"
    _description = "Historial de facturas por orden"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        required=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        related="sale_order_id.partner_id",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        related="sale_order_id.company_id",
        readonly=True,
    )
    line_ids = fields.One2many(
        "sng.return.invoice.history.wizard.line",
        "wizard_id",
        string="Lineas de factura",
    )
    info_message = fields.Text(string="Mensaje", readonly=True)
    invoice_count = fields.Integer(
        string="Facturas",
        compute="_compute_totals",
    )
    total_lines = fields.Integer(
        string="Lineas",
        compute="_compute_totals",
    )
    total_amount = fields.Monetary(
        string="Total",
        compute="_compute_totals",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        compute="_compute_currency_id",
    )

    @api.depends("sale_order_id.currency_id")
    def _compute_currency_id(self):
        for wizard in self:
            wizard.currency_id = wizard.sale_order_id.currency_id

    @api.depends("line_ids.invoice_id", "line_ids.price_subtotal")
    def _compute_totals(self):
        for wizard in self:
            wizard.invoice_count = len(wizard.line_ids.mapped("invoice_id"))
            wizard.total_lines = len(wizard.line_ids)
            wizard.total_amount = sum(wizard.line_ids.mapped("price_subtotal"))

    @api.model
    def _get_related_invoices(self, sale_order):
        sale_order.ensure_one()
        move_model = self.env["account.move"]
        commercial_partner = sale_order.partner_id.commercial_partner_id

        invoices = sale_order.invoice_ids.filtered(
            lambda move: move.move_type in ("out_invoice", "out_refund")
        )
        invoices |= move_model.search([
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("company_id", "=", sale_order.company_id.id),
            ("line_ids.sale_line_ids.order_id", "=", sale_order.id),
        ])
        if sale_order.name:
            invoices |= move_model.search([
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("company_id", "=", sale_order.company_id.id),
                ("partner_id", "child_of", commercial_partner.id),
                ("invoice_origin", "ilike", sale_order.name),
            ])
        return invoices.sorted(lambda move: move.invoice_date or move.date or fields.Date.today(), reverse=True)

    @api.model
    def _build_invoice_line_commands(self, sale_order_id):
        sale_order = self.env["sale.order"].browse(sale_order_id)
        invoices = self._get_related_invoices(sale_order)

        commands = []
        for invoice in invoices:
            invoice_lines = invoice.invoice_line_ids.filtered(lambda line: line.display_type not in ('line_section', 'line_note'))
            for invoice_line in invoice_lines:
                commands.append((0, 0, {
                    "invoice_id": invoice.id,
                    "invoice_date": invoice.invoice_date or invoice.date,
                    "product_id": invoice_line.product_id.id,
                    "quantity": invoice_line.quantity,
                    "uom_id": invoice_line.product_uom_id.id,
                    "price_unit": invoice_line.price_unit,
                    "price_subtotal": invoice_line.price_subtotal,
                    "currency_id": invoice.currency_id.id,
                }))
        return commands

    def action_reload_lines(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("Debe seleccionar una orden de venta."))
        self.line_ids.unlink()
        self.line_ids = self._build_invoice_line_commands(self.sale_order_id.id)
        self.info_message = False
        if not self.line_ids:
            self.info_message = _(
                "No se encontraron facturas vinculadas a esta orden. "
                "La orden puede estar marcada como facturada, pero no existe una relacion real con facturas en Odoo."
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "sng.return.invoice.history.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class SngReturnInvoiceHistoryWizardLine(models.TransientModel):
    _name = "sng.return.invoice.history.wizard.line"
    _description = "Linea de historial de factura"
    _order = "invoice_date desc, invoice_id desc, id desc"

    wizard_id = fields.Many2one(
        "sng.return.invoice.history.wizard",
        required=True,
        ondelete="cascade",
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
    )
    invoice_date = fields.Date(string="Fecha")
    product_id = fields.Many2one("product.product", string="Producto")
    quantity = fields.Float(
        string="Cantidad",
        digits="Product Unit of Measure",
    )
    uom_id = fields.Many2one("uom.uom", string="UdM")
    price_unit = fields.Float(
        string="Precio Unitario",
        digits="Product Price",
    )
    price_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
    )
    state = fields.Selection(
        related="invoice_id.state",
        string="Estado",
        readonly=True,
    )
    payment_state = fields.Selection(
        related="invoice_id.payment_state",
        string="Estado de pago",
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        required=True,
    )

    def action_open_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "new",
        }
