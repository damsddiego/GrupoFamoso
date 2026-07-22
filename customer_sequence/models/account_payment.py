# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    partner_unique_id = fields.Char(
        string='Código cliente',
        related='partner_id.unique_id',
        store=True,
        index=True,
    )
