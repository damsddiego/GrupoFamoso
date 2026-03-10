# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo import api, fields, models, _
from odoo.osv import expression
from ast import literal_eval


class SalesCommissionAnalysis(models.Model):
    _name = 'sales.commission.analysis'
    _description = 'Sales Commission Analysis'

    name = fields.Char(string='Description', required=True)
    date = fields.Date(string='Date', required=True, help="That is the date of the make Commission.")
    #default=lambda self: fields.Date.context_today(self).replace(month=1, day=1),
    sales_person_id = fields.Many2one('res.partner', 'Sales Person', required=True, domain="[('is_salesperson', '=', True)]")
    move_id = fields.Many2one('account.move', 'Inv Ref.')
    sale_order_id = fields.Many2one('sale.order', 'Order Ref.')
    commission_id = fields.Many2one('sales.commission', 'Commission Name')
    commission_type = fields.Selection([('standard', 'Standard'),('partner_based','Partner Based'), ('product_category_margin','Product/ Product Category/ Margin Based')], string="Commission Type")
    product_id = fields.Many2one('product.product', string='Product')
    partner_id = fields.Many2one('res.partner', string='Partner')
    partner_type = fields.Char(string='Partner Type')
    category_id = fields.Many2one('product.category', string='Category')
    #standard
    commission_amount = fields.Float(string='Commission Amount', copy=False)
    currency_id = fields.Many2one(related="commission_id.currency_id")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
