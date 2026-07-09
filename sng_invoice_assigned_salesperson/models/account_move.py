from odoo import api, models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    assigned_salesperson_id = fields.Many2one(
        'res.partner',
        string='Assigned Salesperson',
        compute='_compute_assigned_salesperson_id',
        store=True,
        readonly=True,
        help="The salesperson assigned to this customer.",
    )

    @api.depends('partner_id', 'company_id')
    def _compute_assigned_salesperson_id(self):
        for move in self:
            if move.partner_id and move.company_id:
                move.assigned_salesperson_id = move.partner_id.with_company(move.company_id).assigned_salesperson_id
            else:
                move.assigned_salesperson_id = False
