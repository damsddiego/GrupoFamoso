from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    assigned_salesperson_id = fields.Many2one(
        'res.partner',
        string='Assigned Salesperson',
        related='partner_id.assigned_salesperson_id',
        store=True,
        readonly=True,
        help="The salesperson assigned to this customer."
    )
