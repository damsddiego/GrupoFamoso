# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup#use <> tags in msg 
import base64
import xlwt
import time

class SalesCommissionReportExcel(models.TransientModel):
    _name= "sales.commission.report.excel"
    _description= "sales.commission.report.excel"

    excel_file = fields.Binary(string="Excel Report")
    file_name = fields.Char(string="Report File Name", size=64, readonly=True)


class SalesCommissionReportWiz(models.TransientModel):
    _name = 'sales.commission.report.wiz'
    _description = 'Sales Commission Report Wizard'

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True, default=fields.datetime.today())
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    salesperson_ids = fields.Many2many('res.partner', 'partner_sales_commission_wiz_rel', 'partner_id', 'commission_report_wiz_id', string='Sales Persons', domain="[('is_salesperson', '=', True)]")
    commission_type = fields.Selection([('standard', 'Standard'),('partner_based','Partner Based'), ('product_category_margin','Product/ Product Category/ Margin Based')], string="Commission Type")
    
    commission_type_1 = fields.Boolean('Standard', default=True)
    commission_type_2 = fields.Boolean('Partner Based',default=True)
    commission_type_3 = fields.Boolean('Product/ Product Category/ Margin Based',default=True)
    partner_ids = fields.Many2many('res.partner', 'partner_customer_sales_commission_wiz_rel', 'partner_id', 'commission_report_wiz_id', string='Partners for Partner Based commission')

    def _get_report_salespersons(self):
        self.ensure_one()
        if self.salesperson_ids:
            return self.salesperson_ids
        analysis_domain = [
            ('sales_person_id', '!=', False),
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date),
        ]
        sales_persons = self.env['sales.commission.analysis'].search(analysis_domain).mapped('sales_person_id')
        if sales_persons:
            return sales_persons
        return self.env['res.partner'].sudo().search([('is_salesperson', '=', True)])

    def _build_contexts(self, data):
        result = {}
        result['start_date'] = data['form']['start_date'] or False
        result['end_date'] = data['form']['end_date'] or False
        result['salesperson_ids'] = data['form']['salesperson_ids'] or False
        result['partner_ids'] = data['form']['partner_ids'] or False
        result['commission_type'] = data['form']['commission_type'] or False
        return result

    def print_pdf_report(self):
        data = {}
        self.ensure_one()
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['start_date', 'end_date', 'salesperson_ids','partner_ids','commission_type'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang') or 'en_US')
        return self.env.ref('sales_commission_omax.sales_commission_report_menu_id').report_action(self, data=data, config=False)

    def print_excel_report(self):
        workbook = xlwt.Workbook()
        style = xlwt.XFStyle()
        style_center = xlwt.easyxf('align:vertical center, horizontal center; font:bold on; pattern: pattern solid, fore_colour gray25; border: top thin, bottom thin, right thin, left thin;')
        style_company_title = xlwt.easyxf('font:height 300, bold on; align:horizontal center, vertical center; pattern: pattern solid, fore_color white; border: top thin, bottom thin, right thin, left thin; ')
        style_commission_report_title = xlwt.easyxf('font:height 250, bold on; align:horizontal center, vertical center; pattern: pattern solid, fore_color white; border: top thin, bottom thin, right thin, left thin; ')
        style_sub_title = xlwt.easyxf('font:height 220, bold on; align:horizontal center, vertical center; pattern: pattern solid, fore_color white; border: top thin, bottom thin, right thin, left thin; ')
        style_total = xlwt.easyxf('align: horiz right; font:bold on; pattern: pattern solid, fore_colour gray25; border: top thin, bottom thin, right thin, left thin;')
        style_total_label = xlwt.easyxf('font: bold on; align:horiz right; border: top thin, bottom thin, right thin, left thin;')
        style_amount_right = xlwt.easyxf('align:horiz right;')
        style_date_range = xlwt.easyxf('font: bold on; align:vertical center, horizontal center;')
        style_border = xlwt.easyxf('border: top thin, bottom thin, right thin, left thin; align:vertical center, horizontal center;')
        font = xlwt.Font()
        font.name = 'Times New Roman'
        font.bold = True
        font.height = 250
        style.font = font
        worksheet = workbook.add_sheet('Sheet 1')
        worksheet.write_merge(0,1,0,7,self.env.user.company_id.name,style_company_title)
        worksheet.write_merge(2,3,0,7,'Sales Commission Report',style_commission_report_title)
        start_date = self.start_date.strftime("%d/%m/%Y")
        end_date = self.end_date.strftime("%d/%m/%Y")
        worksheet.write_merge(4,4,1,6,start_date + ' to ' + end_date,style_date_range)
        ####
        sales_persons = self._get_report_salespersons()
        row = 5
        for sales_person in sales_persons:
            worksheet.write_merge(row,row+1, 0,7,'Salesperson : '+ str(sales_person.name),style_sub_title)
            row +=2
            col = 0
            records = self.get_sales_commission_data(self.start_date, self.end_date, sales_person)
            if records:
                worksheet.write(row, col, 'Date', style_center)
                col += 1
                worksheet.write(row, col, 'Name', style_center)
                worksheet.col(col).width = 256 * 35
                col += 1
                worksheet.write(row, col, 'Invoice/Sales Ref.', style_center)
                worksheet.col(col).width = 256 * 18
                col += 1
                worksheet.write(row, col, 'Commission Name.', style_center)
                worksheet.col(col).width = 256 * 24
                col += 1
                worksheet.write(row, col, 'Commission Type', style_center)
                worksheet.col(col).width = 256 * 30
                col += 1
                worksheet.write(row, col, 'Product/Category', style_center)
                worksheet.col(col).width = 256 * 22
                col += 1
                worksheet.write(row, col, 'Partner', style_center)
                col += 1
                worksheet.write(row, col, 'Amount', style_center)
                col += 1
                row += 1
                col = 0
            total_commission = 0
            for rec in records:
                worksheet.write(row, col, time.strftime('%d/%m/%Y',time.strptime(str(rec.date), '%Y-%m-%d')))
                col += 1
                worksheet.write(row, col, str(rec.name))
                col += 1
                if rec.move_id:
                    worksheet.write(row, col, str(rec.move_id.name))
                if rec.sale_order_id:
                    worksheet.write(row, col, str(rec.sale_order_id.name))
                col += 1
                worksheet.write(row, col, str(rec.commission_id.name))
                col += 1
                commission_type = dict(rec._fields['commission_type'].selection).get(rec.commission_type)
                worksheet.write(row, col, str(commission_type))
                col += 1
                if rec.product_id:
                    worksheet.write(row, col, str(rec.product_id.display_name))
                    col += 1
                elif rec.category_id:
                    worksheet.write(row, col, str(rec.category_id.display_name))
                    col += 1
                else:
                    col += 1
                if rec.partner_id:
                    worksheet.write(row, col, str(rec.partner_id.name))
                col += 1
                currency_symbol = rec.currency_id.symbol
                if rec.currency_id.position == 'before':
                    worksheet.write(row, col, currency_symbol + "{:,.2f}".format(rec.commission_amount), style_amount_right)
                else:
                    worksheet.write(row, col, "{:,.2f}".format(rec.commission_amount) + currency_symbol, style_amount_right)
                total_commission += rec.commission_amount
                row += 1
                col = 0
                #
            
            worksheet.write_merge(row,row,0,6,'Total Commission',style_total_label)
            col = 7
            if total_commission:
                if rec.currency_id.position == 'before':
                    worksheet.write(row, col, currency_symbol + "{:,.2f}".format(total_commission),style_total)
                else:
                    worksheet.write(row, col, "{:,.2f}".format(total_commission) + currency_symbol,style_total)
            else:
                worksheet.write(row, col, "{:,.2f}".format(total_commission),style_total)
            row += 2
            col = 0
            
        ####
        filename = 'Sales Commission Report.xls'
        workbook.save("/tmp/Sales Commission Report.xls")
        file = open("/tmp/Sales Commission Report.xls", "rb")
        file_data = file.read()
        #out = base64.encodestring(file_data)
        out = base64.encodebytes(file_data)#python3.8 support
        
        #when wizard still open and try to change M2M field then try to print that time updated thing not apply on current obj's excel_file field so, not getting correnct value in excel download. that's the reason make new object to save and download excel file.
        #In new object every time add new effected correctly and getting correct excel report
        export_obj = self.env['sales.commission.report.excel'].create({'excel_file': out, 'file_name': filename})
        active_id = self.ids[0]
        #if self.excel_file:
        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=sales.commission.report.excel&download=true&field=excel_file&id=%s&filename=%s' % (export_obj.id, filename),
            'target': 'new',#self
        }


    def get_sales_commission_data(self, start_date, end_date, sales_person):
        records = self.env["sales.commission.analysis"]
        domain = [('date','>=',start_date), ('date','<=',end_date), ('sales_person_id','=',sales_person.id)]
        if self.commission_type_1:
            new_domain = domain + [('commission_type','=','standard')]
            records += self.env["sales.commission.analysis"].search(new_domain)
        if self.commission_type_2:
            new_domain = []
            new_domain = domain + [('commission_type','=','partner_based')]
            if self.partner_ids:
                new_domain += [('partner_id','in',self.partner_ids.ids)]
            records += self.env["sales.commission.analysis"].search(new_domain)
        if self.commission_type_3:
            new_domain = domain + [('commission_type','=','product_category_margin')]
            records += self.env["sales.commission.analysis"].search(new_domain)
        return records
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
