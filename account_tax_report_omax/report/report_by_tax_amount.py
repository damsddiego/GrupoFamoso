# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from odoo import api, models, _
from odoo.exceptions import UserError
from datetime import datetime
from json import dumps
import ast
import json


class ReportBy_account_tax_reportCs(models.AbstractModel):
    _name = 'report.account_tax_report_omax.account_report_tax_tmpl_id'

    def _get_selected_company(self,company_ids):
        company_obj = self.env.company
        companys = company_obj.sudo().browse(company_ids)
        return companys 
        
    def _get_account_invoices(self,company,start_date,end_date):
        account_invoices = self.env['account.move'].sudo().search([('invoice_date', '>=', start_date),('invoice_date', '<=', end_date), ('state', '!=', 'draft'),('move_type','in',['out_invoice', 'out_refund','in_invoice', 'in_refund']),('company_id','=',company.id)]).filtered(lambda l: l.amount_tax)
        return account_invoices 
    
    def _get_partners(self,account_invoices,partner_ids,report_for):
        partners = account_invoices.mapped('partner_id')
        if partner_ids and report_for == 'partners':
            partners = partners.sudo().filtered(lambda partner: partner.id in partner_ids)    
        return partners
        
    def _get_product_categories(self,account_invoices,product_category_ids,report_for):
        categories = account_invoices.mapped('invoice_line_ids.product_id.categ_id')
        if product_category_ids and report_for == 'productCategory':
            categories = categories.sudo().filtered(lambda category: category.id in product_category_ids)    
        return categories
        
    def _get_products(self,account_invoices,product_ids,report_for):
        products = account_invoices.mapped('invoice_line_ids').filtered(lambda line: line.tax_ids).mapped('product_id')
        if product_ids and report_for == 'products':
            products = products.sudo().filtered(lambda product: product.id in product_ids)    
        return products
        
    def _get_sales_team(self,account_invoices,sales_team_ids,report_for):
        sales_team = account_invoices.mapped('team_id')
        if sales_team_ids and report_for == 'sales_team':
            sales_team = sales_team.sudo().filtered(lambda sale_team: sale_team.id in sales_team_ids)    
        return sales_team
        
    def _get_sales_person(self,account_invoices,salesperson_ids,report_for):
        sales_person = account_invoices.mapped('invoice_user_id')
        if salesperson_ids and report_for == 'sales_person':
            sales_person = sales_person.sudo().filtered(lambda sp: sp.id in salesperson_ids)    
        return sales_person
        
    def _get_move_taxes(self,account_invoices,tax_ids,report_for):
        taxes = account_invoices.mapped('invoice_line_ids.tax_ids')
        if tax_ids and report_for == 'taxes':
            taxes = taxes.sudo().filtered(lambda tax: tax.id in tax_ids)    
        return taxes
        
    def _get_tax_name(self,invoices):
        inv_tax = []
        for account_invoice in invoices:
            taxes = account_invoice.tax_totals
            if taxes['subtotals'][0]['tax_groups']: 
                for tax in taxes['subtotals'][0]['tax_groups']:
                    if tax['group_name'] not in inv_tax:
                        inv_tax.append(tax['group_name'])
        return inv_tax
    
    def _get_product_tax_name(self,invoices,product):
        inv_tax = []
        for account_invoice in invoices:
            taxes = account_invoice.tax_totals
            product_line = account_invoice.invoice_line_ids.sudo().filtered(lambda inv : inv.product_id.id == product.id)
            if taxes['subtotals'][0]['tax_groups']: 
                for tax in taxes['subtotals'][0]['tax_groups']:
                    if tax['group_name'] not in inv_tax:
                        #add tax based on filtered product tax
                        if any(pro_tax in tax.get('involved_tax_ids') for pro_tax in product_line.tax_ids.ids):
                            inv_tax.append(tax['group_name'])
        return inv_tax
        
    def _get_tax_detail(self,invoices,tax_rec):
        inv_tax = []
        for account_invoice in invoices:
            taxes = account_invoice.tax_totals
            if taxes['subtotals'][0]['tax_groups']: 
                for tax in taxes['subtotals'][0]['tax_groups']:
                    if tax['group_name'] not in inv_tax:
                        if tax_rec.id in tax.get('involved_tax_ids'): #add tax based on filtered tax
                            inv_tax.append(tax['group_name'])
        return inv_tax
        
    def _filter_inv_on_tax(self,tax,invoice):
        line = []
        for inv in invoice:
            in_out_refund = inv.move_type in ['out_refund','in_refund']
            taxes = inv.tax_totals
            if taxes['subtotals'][0]['tax_groups']:
                for tax_group in taxes['subtotals'][0]['tax_groups']:
                    if tax_group.get('group_name') == tax:
                        group = tax_group

                        # Get all amount fields from invoice with safe access
                        amount_discount_electronic_invoice = getattr(inv, 'amount_discount_electronic_invoice', 0.0) or 0.0
                        amount_iva_returned = getattr(inv, 'amount_iva_returned', 0.0) or 0.0
                        amount_paid = getattr(inv, 'amount_paid', 0.0) or 0.0
                        amount_residual = getattr(inv, 'amount_residual', 0.0) or 0.0
                        amount_residual_signed = getattr(inv, 'amount_residual_signed', 0.0) or 0.0
                        amount_subtotal_without_iva_returned = getattr(inv, 'amount_subtotal_without_iva_returned', 0.0) or 0.0
                        amount_tax = getattr(inv, 'amount_tax', 0.0) or 0.0
                        amount_tax_electronic_invoice = getattr(inv, 'amount_tax_electronic_invoice', 0.0) or 0.0
                        amount_tax_signed = getattr(inv, 'amount_tax_signed', 0.0) or 0.0
                        amount_total = getattr(inv, 'amount_total', 0.0) or 0.0
                        amount_total_in_currency_signed = getattr(inv, 'amount_total_in_currency_signed', 0.0) or 0.0
                        amount_total_signed = getattr(inv, 'amount_total_signed', 0.0) or 0.0
                        amount_untaxed = getattr(inv, 'amount_untaxed', 0.0) or 0.0
                        amount_untaxed_in_currency_signed = getattr(inv, 'amount_untaxed_in_currency_signed', 0.0) or 0.0
                        electronic_invoice_return_message = getattr(inv, 'electronic_invoice_return_message', '') or ''

                        # Apply refund logic to amounts
                        discount_adjusted = amount_discount_electronic_invoice if not in_out_refund else -abs(amount_discount_electronic_invoice)
                        total_signed_adjusted = amount_total_signed if not in_out_refund else -abs(amount_total_signed)

                        # Calculate Sub Total (Total Signed + Discount Electronic Invoice)
                        sub_total = total_signed_adjusted + discount_adjusted

                        val = {
                            'name' : inv.partner_id.name,
                            'ref' : inv.name,
                            'inv_date' : inv.invoice_date.strftime("%d/%m/%y"),
                            'sub_total' : sub_total,
                            'amount_discount_electronic_invoice' : discount_adjusted,
                            'amount_iva_returned' : amount_iva_returned if not in_out_refund else -abs(amount_iva_returned),
                            'amount_paid' : amount_paid if not in_out_refund else -abs(amount_paid),
                            'amount_residual' : amount_residual if not in_out_refund else -abs(amount_residual),
                            'amount_residual_signed' : amount_residual_signed if not in_out_refund else -abs(amount_residual_signed),
                            'amount_subtotal_without_iva_returned' : amount_subtotal_without_iva_returned if not in_out_refund else -abs(amount_subtotal_without_iva_returned),
                            'amount_tax' : amount_tax if not in_out_refund else -abs(amount_tax),
                            'amount_tax_electronic_invoice' : amount_tax_electronic_invoice if not in_out_refund else -abs(amount_tax_electronic_invoice),
                            'amount_tax_signed' : amount_tax_signed if not in_out_refund else -abs(amount_tax_signed),
                            'amount_total' : amount_total if not in_out_refund else -abs(amount_total),
                            'amount_total_in_currency_signed' : amount_total_in_currency_signed if not in_out_refund else -abs(amount_total_in_currency_signed),
                            'amount_total_signed' : total_signed_adjusted,
                            'amount_untaxed' : amount_untaxed if not in_out_refund else -abs(amount_untaxed),
                            'amount_untaxed_in_currency_signed' : amount_untaxed_in_currency_signed if not in_out_refund else -abs(amount_untaxed_in_currency_signed),
                            'electronic_invoice_return_message' : electronic_invoice_return_message,
                            # Currency formatted values
                            'sub_total_currency' : inv.company_id.currency_id.format(sub_total),
                            'amount_discount_electronic_invoice_currency' : inv.company_id.currency_id.format(discount_adjusted),
                            'amount_iva_returned_currency' : inv.company_id.currency_id.format(amount_iva_returned) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_iva_returned)),
                            'amount_paid_currency' : inv.company_id.currency_id.format(amount_paid) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_paid)),
                            'amount_residual_currency' : inv.company_id.currency_id.format(amount_residual) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_residual)),
                            'amount_residual_signed_currency' : inv.company_id.currency_id.format(amount_residual_signed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_residual_signed)),
                            'amount_subtotal_without_iva_returned_currency' : inv.company_id.currency_id.format(amount_subtotal_without_iva_returned) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_subtotal_without_iva_returned)),
                            'amount_tax_currency' : inv.company_id.currency_id.format(amount_tax) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_tax)),
                            'amount_tax_electronic_invoice_currency' : inv.company_id.currency_id.format(amount_tax_electronic_invoice) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_tax_electronic_invoice)),
                            'amount_tax_signed_currency' : inv.company_id.currency_id.format(amount_tax_signed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_tax_signed)),
                            'amount_total_currency' : inv.company_id.currency_id.format(amount_total) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_total)),
                            'amount_total_in_currency_signed_currency' : inv.company_id.currency_id.format(amount_total_in_currency_signed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_total_in_currency_signed)),
                            'amount_total_signed_currency' : inv.company_id.currency_id.format(total_signed_adjusted),
                            'amount_untaxed_currency' : inv.company_id.currency_id.format(amount_untaxed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_untaxed)),
                            'amount_untaxed_in_currency_signed_currency' : inv.company_id.currency_id.format(amount_untaxed_in_currency_signed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_untaxed_in_currency_signed)),
                        }
                        line.append(val)
        return line
        
    def _filter_inv_on_product_tax(self,tax,invoice,product_rec=None,category_rec=None):
        line = []
        for inv in invoice:
            in_out_refund = inv.move_type in ['out_refund','in_refund']
            product_line = None
            if product_rec:
                product_line = inv.invoice_line_ids.sudo().filtered(lambda i : i.product_id.id == product_rec.id)
            if category_rec:
                product_line = inv.invoice_line_ids.sudo().filtered(lambda i : i.product_id.categ_id.id == category_rec.id)

            taxes = inv.tax_totals
            if taxes['subtotals'][0]['tax_groups']:
                for tax_group in taxes['subtotals'][0]['tax_groups']:
                    if tax_group.get('group_name') == tax:
                        base_amount = 0
                        tax_amount = 0
                        for product in product_line:
                            product_line_tax = product.tax_ids.sudo().filtered(lambda i : i.tax_group_id.name == tax)
                            tax_persantage = product_line_tax.amount
                            if product_line_tax and tax_persantage:
                                base_amount += product.price_subtotal
                                tax_amount = base_amount * (tax_persantage / 100)
                        if base_amount and tax_amount:
                            if inv.currency_id != inv.company_id.currency_id:
                                base_amount = inv.currency_id._convert(base_amount, inv.company_id.currency_id, inv.company_id, inv.invoice_date or inv.date)
                                tax_amount = inv.currency_id._convert(tax_amount, inv.company_id.currency_id, inv.company_id, inv.invoice_date or inv.date)

                            # Get all amount fields from invoice with safe access
                            amount_discount_electronic_invoice = getattr(inv, 'amount_discount_electronic_invoice', 0.0) or 0.0
                            amount_iva_returned = getattr(inv, 'amount_iva_returned', 0.0) or 0.0
                            amount_paid = getattr(inv, 'amount_paid', 0.0) or 0.0
                            amount_residual = getattr(inv, 'amount_residual', 0.0) or 0.0
                            amount_residual_signed = getattr(inv, 'amount_residual_signed', 0.0) or 0.0
                            amount_subtotal_without_iva_returned = getattr(inv, 'amount_subtotal_without_iva_returned', 0.0) or 0.0
                            amount_tax = getattr(inv, 'amount_tax', 0.0) or 0.0
                            amount_tax_electronic_invoice = getattr(inv, 'amount_tax_electronic_invoice', 0.0) or 0.0
                            amount_tax_signed = getattr(inv, 'amount_tax_signed', 0.0) or 0.0
                            amount_total = getattr(inv, 'amount_total', 0.0) or 0.0
                            amount_total_in_currency_signed = getattr(inv, 'amount_total_in_currency_signed', 0.0) or 0.0
                            amount_total_signed = getattr(inv, 'amount_total_signed', 0.0) or 0.0
                            amount_untaxed = getattr(inv, 'amount_untaxed', 0.0) or 0.0
                            amount_untaxed_in_currency_signed = getattr(inv, 'amount_untaxed_in_currency_signed', 0.0) or 0.0
                            electronic_invoice_return_message = getattr(inv, 'electronic_invoice_return_message', '') or ''

                            # Apply refund logic to amounts
                            discount_adjusted = amount_discount_electronic_invoice if not in_out_refund else -abs(amount_discount_electronic_invoice)
                            total_signed_adjusted = amount_total_signed if not in_out_refund else -abs(amount_total_signed)

                            # Calculate Sub Total (Total Signed + Discount Electronic Invoice)
                            sub_total = total_signed_adjusted + discount_adjusted

                            val = {
                                'name' : inv.partner_id.name,
                                'ref' : inv.name,
                                'inv_date' : inv.invoice_date.strftime("%d/%m/%y"),
                                'sub_total' : sub_total,
                                'amount_discount_electronic_invoice' : discount_adjusted,
                                'amount_iva_returned' : amount_iva_returned if not in_out_refund else -abs(amount_iva_returned),
                                'amount_paid' : amount_paid if not in_out_refund else -abs(amount_paid),
                                'amount_residual' : amount_residual if not in_out_refund else -abs(amount_residual),
                                'amount_residual_signed' : amount_residual_signed if not in_out_refund else -abs(amount_residual_signed),
                                'amount_subtotal_without_iva_returned' : amount_subtotal_without_iva_returned if not in_out_refund else -abs(amount_subtotal_without_iva_returned),
                                'amount_tax' : amount_tax if not in_out_refund else -abs(amount_tax),
                                'amount_tax_electronic_invoice' : amount_tax_electronic_invoice if not in_out_refund else -abs(amount_tax_electronic_invoice),
                                'amount_tax_signed' : amount_tax_signed if not in_out_refund else -abs(amount_tax_signed),
                                'amount_total' : amount_total if not in_out_refund else -abs(amount_total),
                                'amount_total_in_currency_signed' : amount_total_in_currency_signed if not in_out_refund else -abs(amount_total_in_currency_signed),
                                'amount_total_signed' : total_signed_adjusted,
                                'amount_untaxed' : amount_untaxed if not in_out_refund else -abs(amount_untaxed),
                                'amount_untaxed_in_currency_signed' : amount_untaxed_in_currency_signed if not in_out_refund else -abs(amount_untaxed_in_currency_signed),
                                'electronic_invoice_return_message' : electronic_invoice_return_message,
                                # Currency formatted values
                                'sub_total_currency' : inv.company_id.currency_id.format(sub_total),
                                'amount_discount_electronic_invoice_currency' : inv.company_id.currency_id.format(discount_adjusted),
                                'amount_iva_returned_currency' : inv.company_id.currency_id.format(amount_iva_returned) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_iva_returned)),
                                'amount_paid_currency' : inv.company_id.currency_id.format(amount_paid) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_paid)),
                                'amount_residual_currency' : inv.company_id.currency_id.format(amount_residual) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_residual)),
                                'amount_residual_signed_currency' : inv.company_id.currency_id.format(amount_residual_signed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_residual_signed)),
                                'amount_subtotal_without_iva_returned_currency' : inv.company_id.currency_id.format(amount_subtotal_without_iva_returned) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_subtotal_without_iva_returned)),
                                'amount_tax_currency' : inv.company_id.currency_id.format(amount_tax) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_tax)),
                                'amount_tax_electronic_invoice_currency' : inv.company_id.currency_id.format(amount_tax_electronic_invoice) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_tax_electronic_invoice)),
                                'amount_tax_signed_currency' : inv.company_id.currency_id.format(amount_tax_signed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_tax_signed)),
                                'amount_total_currency' : inv.company_id.currency_id.format(amount_total) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_total)),
                                'amount_total_in_currency_signed_currency' : inv.company_id.currency_id.format(amount_total_in_currency_signed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_total_in_currency_signed)),
                                'amount_total_signed_currency' : inv.company_id.currency_id.format(total_signed_adjusted),
                                'amount_untaxed_currency' : inv.company_id.currency_id.format(amount_untaxed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_untaxed)),
                                'amount_untaxed_in_currency_signed_currency' : inv.company_id.currency_id.format(amount_untaxed_in_currency_signed) if not in_out_refund else inv.company_id.currency_id.format(-abs(amount_untaxed_in_currency_signed)),
                            }
                            line.append(val)
        return line


                
    @api.model
    def _get_report_values(self, docids, data=None):
        if not data.get('form') or not self.env.context.get('active_model') or not self.env.context.get('active_id'):
            raise UserError(_("Form content is missing, this report cannot be printed."))
        model = self.env.context.get('active_model')
        data = data if data is not None else {}
        docs = self.env[model].browse(self.env.context.get('active_id'))
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data,
            'docs' : docs,
            'get_selected_company': self._get_selected_company,
            'get_account_invoices': self._get_account_invoices,
            'get_partners': self._get_partners,
            'get_product_categories' : self._get_product_categories,
            'get_products': self._get_products,
            'get_sales_team': self._get_sales_team,
            'get_sales_person': self._get_sales_person,
            'get_move_taxes': self._get_move_taxes,
            'get_tax_name': self._get_tax_name,
            'get_product_tax_name': self._get_product_tax_name,
            'get_tax_detail': self._get_tax_detail,
            'filter_inv_on_tax': self._filter_inv_on_tax,
            'filter_inv_on_product_tax': self._filter_inv_on_product_tax,
        }
       

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
