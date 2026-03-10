# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import  fields, models

class FilterCustomerStateMent(models.Model):
    _name = "sh.res.partner.filter.statement"
    _description = "Filter Customer Statement"

    partner_id = fields.Many2one("res.partner", "Partner")
    name = fields.Char("Invoice Number")
    currency_id = fields.Many2one("res.currency", "Currency")
    sh_account = fields.Char("Account")
    sh_filter_invoice_date = fields.Date("Invoice Date")
    sh_filter_due_date = fields.Date("Invoice Due Date")
    sh_filter_amount = fields.Monetary("Total Amount")
    sh_filter_paid_amount = fields.Monetary("Paid Amount")
    sh_filter_balance = fields.Monetary("Balance")
    sh_filter_type = fields.Selection([('a','A'),('b','B')],default="b")

    sh_filter_payment_date=fields.Date("Payment Date")
    sh_filter_payment_ref_no=fields.Char("Payment Ref no.")
    sh_filter_total_balance=fields.Monetary("Total Balance")