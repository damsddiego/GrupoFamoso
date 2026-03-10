# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from odoo import api, models, _
from odoo.exceptions import UserError
from datetime import datetime
from json import dumps
import ast
import json


class Report_sales_commission_wiz_report(models.AbstractModel):
    _name = 'report.sales_commission_omax.sales_commission_report_tmpl_id'
    _description = 'report.sales_commission_omax.sales_commission_report_tmpl_id'

    def _get_report_salespersons(self, docs, data):
        if docs.salesperson_ids:
            return docs.salesperson_ids
        form_data = data.get('form') or {}
        start_date = form_data.get('start_date') or docs.start_date
        end_date = form_data.get('end_date') or docs.end_date
        analysis_domain = [
            ('sales_person_id', '!=', False),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
        ]
        salespersons = self.env['sales.commission.analysis'].search(analysis_domain).mapped('sales_person_id')
        if salespersons:
            return salespersons
        return self.env['res.partner'].sudo().search([('is_salesperson', '=', True)])

    def _get_sales_commission_data(self, start_date, end_date, sales_person, rec):
        records = self.env["sales.commission.analysis"]
        domain = [('date','>=',start_date), ('date','<=',end_date), ('sales_person_id','=',sales_person.id)]
        if rec.commission_type_1:
            new_domain = domain + [('commission_type','=','standard')]
            records += self.env["sales.commission.analysis"].search(new_domain)
        if rec.commission_type_2:
            new_domain = []
            new_domain = domain + [('commission_type','=','partner_based')]
            if rec.partner_ids:
                new_domain += [('partner_id','in',rec.partner_ids.ids)]
            records += self.env["sales.commission.analysis"].search(new_domain)
        if rec.commission_type_3:
            new_domain = domain + [('commission_type','=','product_category_margin')]
            records += self.env["sales.commission.analysis"].search(new_domain)
        return records
                
    @api.model
    def _get_report_values(self, docids, data=None):
        if not data.get('form') or not self.env.context.get('active_model') or not self.env.context.get('active_id'):
            raise UserError(_("Form content is missing, this report cannot be printed."))
        model = self.env.context.get('active_model')
        data = data if data is not None else {}
        docs = self.env[model].browse(self.env.context.get('active_id'))
        salesperson_ids = self._get_report_salespersons(docs, data)
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data,
            'docs' : docs,
            'salesperson_ids':salesperson_ids,
            'get_sales_commission_data':self._get_sales_commission_data,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
