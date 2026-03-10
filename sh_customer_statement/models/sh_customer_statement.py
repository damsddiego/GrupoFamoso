# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import  fields, models


class CustomerStateMent(models.Model):
    _name = "sh.customer.statement"
    _description = "Customer Statement"

    partner_id = fields.Many2one("res.partner", "Partner")
    currency_id = fields.Many2one("res.currency", "Currency")
    name = fields.Char("Invoice Number")
    sh_account = fields.Char("Account")
    sh_customer_invoice_date = fields.Date("Invoice Date")
    sh_customer_due_date = fields.Date("Invoice Due Date")
    sh_customer_amount = fields.Monetary("Total Amount")
    sh_customer_paid_amount = fields.Monetary("Paid Amount")
    sh_customer_balance = fields.Monetary("Balance")

    sh_payment_reference=fields.Char("Payment Refrence")
    sh_payment_date=fields.Date("Payment Date")
    sh_total_balance =fields.Monetary()
