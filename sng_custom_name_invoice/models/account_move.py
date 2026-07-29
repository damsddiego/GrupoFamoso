from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_commercial_name = fields.Char(
        string='Nombre Comercial',
        related='partner_id.commercial_name',
        store=True,
        readonly=True,
    )
