from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    effective_salesperson_id = fields.Many2one(
        'res.partner',
        string='Effective Salesperson',
        compute='_compute_effective_salesperson_id',
        store=True,
        index=True,
        help="Shows salesperson_id if set, otherwise falls back to assigned_salesperson_id from customer"
    )

    @api.depends(
        'salesperson_id', 'salesperson_id.is_salesperson',
        'assigned_salesperson_id', 'assigned_salesperson_id.is_salesperson',
    )
    def _compute_effective_salesperson_id(self):
        """Compute effective salesperson using fallback logic.

        Priority:
        1. salesperson_id (from sales_commission_omax), if a real salesperson
        2. assigned_salesperson_id (from customer's assigned salesperson),
           if a real salesperson

        Partners not flagged as salespersons (e.g. the invoicing user set
        as fallback by sales_commission_omax) are ignored, leaving the
        field empty so the invoice groups under 'None' / 'Sin asignar'.
        """
        for move in self:
            effective = False
            for candidate in (move.salesperson_id, move.assigned_salesperson_id):
                if candidate and candidate.is_salesperson:
                    effective = candidate
                    break
            move.effective_salesperson_id = effective
