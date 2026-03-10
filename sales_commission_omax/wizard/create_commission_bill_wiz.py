# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup#use <> tags in msg 


class CreateCommissionBillWiz(models.TransientModel):
    _name = 'create.commission.bill.wiz'
    _description = 'Bill Sales Commission Analysis'

    #date_order = fields.Datetime(string='Date', required=True, default=datetime.datetime.now())
    group_by_commission_type = fields.Boolean('Group by Commission type')
    bill_create_action = fields.Selection(selection=[
            ('remove', 'Remove Selected Records'),
            ('cancel', 'Cancel Selected Records'),
        ], string='After Bill Creation', required=True, default='cancel')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    account_id = fields.Many2one('account.account','Commission Account')

    def create_bill(self):
        active_ids = self._context.get('active_ids')
        vals = {}
        bill_ids = self.env['account.move']
        if active_ids:
            commission_analysis = self.env['sales.commission.analysis'].browse(active_ids)
            sales_persons = commission_analysis.mapped('sales_person_id')
            for user in sales_persons:
                user_commission_analysis = commission_analysis.filtered(lambda l: l.sales_person_id.id == user.id)
                #group by Commission Type
                if self.group_by_commission_type:
                    commission_type = set(user_commission_analysis.mapped('commission_type'))
                    for comm_type in commission_type:
                        comm_type_commission_analysis = user_commission_analysis.filtered(lambda l: l.commission_type == comm_type)
                        if comm_type_commission_analysis:
                            bill_vals = {
                                'move_type': 'in_invoice',
                                'partner_id': user.id,
                                'invoice_date': fields.Date.context_today(self),
                                'state': 'draft',
                                'date': fields.Date.context_today(self),
                                'company_id': self.env.company.id,
                                'created_by_commission':True,
                            }
                            move_line_list = []
                            for line in comm_type_commission_analysis:
                                commission_product = self.env.ref('sales_commission_omax.sales_commission_product_0')
                                line_vals = {
                                    'product_id': commission_product.id,
                                    'name': line.name,
                                    'quantity': 1,
                                    'product_uom_id': commission_product.uom_id.id,
                                    'price_unit': line.commission_amount,
                                    'display_type':'product',
                                }
                                if self.account_id:
                                    line_vals['account_id'] = self.account_id.id
                                move_line_list.append([0, 0, line_vals])
                            if move_line_list:
                                bill_vals.update({'invoice_line_ids':move_line_list})
                                bill = self.env['account.move'].create(bill_vals)
                                bill_ids += bill
                else:#NOT group by Commission Type
                    bill_vals = {
                        'move_type': 'in_invoice',
                        'partner_id': user.id,
                        'invoice_date': fields.Date.context_today(self),
                        'state': 'draft',
                        'date': fields.Date.context_today(self),
                        'company_id': self.env.company.id,
                        'created_by_commission':True,
                    }
                    move_line_list = []
                    for line in user_commission_analysis:
                        commission_product = self.env.ref('sales_commission_omax.sales_commission_product_0')
                        line_vals = {
                            'product_id': commission_product.id,
                            'name': line.name,
                            'quantity': 1,
                            'product_uom_id': commission_product.uom_id.id,
                            'price_unit': line.commission_amount,
                            'display_type':'product',
                        }
                        if self.account_id:
                            line_vals['account_id'] = self.account_id.id
                        move_line_list.append([0, 0, line_vals])
                    if move_line_list:
                        bill_vals.update({'invoice_line_ids':move_line_list})
                        bill = self.env['account.move'].create(bill_vals)
                        bill_ids += bill
        action = self.env.ref('account.action_move_in_invoice_type').read()[0]
        if len(bill_ids) > 1:
            action['domain'] = [('id', 'in', bill_ids.ids)]
        elif bill_ids:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = bill_ids.id
        return action

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
