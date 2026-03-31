from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    assigned_salesperson_id = fields.Many2one(
        "res.partner",
        string="Assigned Salesperson",
        related="partner_id.assigned_salesperson_id",
        store=True,
        readonly=True,
        help="The salesperson assigned to this customer.",
    )
