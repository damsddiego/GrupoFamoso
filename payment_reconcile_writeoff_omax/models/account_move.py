# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    writeoff_notes = fields.Char('Writeoff Notes')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
