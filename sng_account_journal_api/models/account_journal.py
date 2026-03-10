from odoo import models, fields

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    include_in_app = fields.Boolean(string='Incluir en App')
