# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import  fields, models

class CustomerDueStateMent(models.Model):
    _name = "sh.customer.due.statement"
    _description = "Customer Due Statement"

    partner_id = fields.Many2one("res.partner", "Partner")
    name = fields.Char("Invoice Number")
    currency_id = fields.Many2one("res.currency", "Currency")
    sh_account = fields.Char("Account")
    sh_today = fields.Date("Today")
    sh_due_customer_invoice_date = fields.Date("Invoice Date")
    sh_due_customer_due_date = fields.Date("Invoice Due Date")
    sh_due_customer_amount = fields.Monetary("Total Amount")
    sh_due_customer_paid_amount = fields.Monetary("Paid Amount")
    sh_due_customer_balance = fields.Monetary("Balance")
