# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class Partner(models.Model):
    _inherit = "res.partner"

    affiliated = fields.Boolean('Affiliated')
    is_salesperson = fields.Boolean('Is Salesperson', help="Check this box if this contact is a salesperson for commission purposes.")
    assigned_salesperson_id = fields.Many2one('res.partner', 'Assigned Salesperson',
        domain="[('is_salesperson', '=', True)]",
        help="Default salesperson assigned to this customer. This will be automatically set on new sales orders.")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
