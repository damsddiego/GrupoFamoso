from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SngReturnHistoryWizard(models.TransientModel):
    _name = "sng.return.history.wizard"
    _description = "Historial de ventas facturadas"

    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
    )
    return_id = fields.Many2one(
        "sng.return",
        string="Devolucion",
    )
    return_line_id = fields.Many2one(
        "sng.return.line",
        string="Linea de devolucion",
    )
    history_line_ids = fields.One2many(
        "sng.return.history.wizard.line",
        "wizard_id",
        string="Historial",
    )
    total_qty = fields.Float(
        string="Cantidad total",
        compute="_compute_totals",
        digits="Product Unit of Measure",
    )
    order_count = fields.Integer(
        string="Total ordenes",
        compute="_compute_totals",
    )

    @api.depends("history_line_ids.quantity", "history_line_ids.sale_order_id")
    def _compute_totals(self):
        for wizard in self:
            wizard.total_qty = sum(wizard.history_line_ids.mapped("quantity"))
            wizard.order_count = len(wizard.history_line_ids.mapped("sale_order_id"))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        partner_id = res.get("partner_id") or self.env.context.get("default_partner_id")
        product_id = res.get("product_id") or self.env.context.get("default_product_id")
        company_id = res.get("company_id") or self.env.context.get("default_company_id") or self.env.company.id
        if partner_id:
            res["history_line_ids"] = self._build_history_commands(partner_id, product_id, company_id)
        return res

    @api.model
    def _build_history_commands(self, partner_id, product_id=False, company_id=False):
        partner = self.env["res.partner"].browse(partner_id)
        company_id = company_id or self.env.company.id
        domain = [
            ("order_id.partner_id", "child_of", partner.commercial_partner_id.id),
            ("order_id.state", "in", ["sale", "done"]),
            ("order_id.invoice_status", "=", "invoiced"),
            ("company_id", "=", company_id),
            ("display_type", "=", False),
        ]
        if product_id:
            domain.append(("product_id", "=", product_id))

        sale_lines = self.env["sale.order.line"].search(domain)
        sale_lines = sale_lines.sorted(lambda line: line.order_id.date_order or fields.Datetime.now(), reverse=True)

        commands = []
        for sale_line in sale_lines:
            commands.append((0, 0, {
                "sale_order_id": sale_line.order_id.id,
                "date_order": sale_line.order_id.date_order,
                "partner_id": sale_line.order_id.partner_id.id,
                "product_id": sale_line.product_id.id,
                "quantity": sale_line.product_uom_qty,
                "uom_id": sale_line.product_uom.id,
                "price_unit": sale_line.price_unit,
                "price_subtotal": sale_line.price_subtotal,
                "salesperson_id": sale_line.order_id.user_id.id,
            }))
        return commands

    def action_reload_history(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Debe seleccionar un cliente."))
        self.history_line_ids.unlink()
        self.history_line_ids = self._build_history_commands(
            self.partner_id.id,
            self.product_id.id if self.product_id else False,
            self.company_id.id,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "sng.return.history.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class SngReturnHistoryWizardLine(models.TransientModel):
    _name = "sng.return.history.wizard.line"
    _description = "Linea de historial de ventas facturadas"
    _order = "date_order desc, id desc"

    wizard_id = fields.Many2one(
        "sng.return.history.wizard",
        required=True,
        ondelete="cascade",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        required=True,
    )
    date_order = fields.Datetime(string="Fecha")
    partner_id = fields.Many2one("res.partner", string="Cliente")
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
    price_subtotal = fields.Float(
        string="Subtotal",
        digits="Product Price",
    )
    invoice_status = fields.Selection(
        related="sale_order_id.invoice_status",
        string="Estado de factura",
        readonly=True,
    )
    salesperson_id = fields.Many2one("res.users", string="Vendedor")
    invoice_count = fields.Integer(
        string="Facturas",
        compute="_compute_invoice_count",
    )

    @api.depends("sale_order_id")
    def _compute_invoice_count(self):
        invoice_wizard_model = self.env["sng.return.invoice.history.wizard"]
        for line in self:
            invoices = invoice_wizard_model._get_related_invoices(line.sale_order_id)
            line.invoice_count = len(invoices)

    def action_open_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_invoices(self):
        self.ensure_one()
        wizard_model = self.env["sng.return.invoice.history.wizard"]
        line_commands = wizard_model._build_invoice_line_commands(self.sale_order_id.id)
        wizard_vals = {
            "sale_order_id": self.sale_order_id.id,
            "line_ids": line_commands,
        }
        if not line_commands:
            wizard_vals["info_message"] = _(
                "No se encontraron facturas vinculadas a la orden %(order)s. "
                "El pedido puede estar con estado facturado, pero sin facturas relacionadas en la base de datos."
            ) % {"order": self.sale_order_id.name}
        wizard = wizard_model.create(wizard_vals)
        return {
            "type": "ir.actions.act_window",
            "name": _("Historial de facturas"),
            "res_model": "sng.return.invoice.history.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
