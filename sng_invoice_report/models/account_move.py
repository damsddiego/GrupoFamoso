from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    effective_salesperson_id = fields.Many2one(
        'res.partner',
        string='Effective Salesperson',
        compute='_compute_effective_salesperson_id',
        store=False,
        help="Shows salesperson_id if set, otherwise falls back to assigned_salesperson_id from customer"
    )

    @api.depends('salesperson_id', 'assigned_salesperson_id')
    def _compute_effective_salesperson_id(self):
        """Compute effective salesperson using fallback logic.

        Priority:
        1. salesperson_id (from sales_commission_omax)
        2. assigned_salesperson_id (from customer's assigned salesperson)
        """
        for move in self:
            move.effective_salesperson_id = move.salesperson_id or move.assigned_salesperson_id
