# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import  fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sh_customer_statement_auto_send = fields.Boolean(
        'Customer Statement Auto Send')
    filter_only_unpaid_and_send_that = fields.Boolean(string = "Filter Only Unpaid, Send nothing if all invoices are paid")
    sh_customer_statement_action = fields.Selection([('daily', 'Daily'), ('weekly', 'Weekly'), (
        'monthly', 'Monthly'), ('yearly', 'Yearly')], string='Customer Statement Action')
    sh_cus_daily_statement_template_id = fields.Many2one(
        'mail.template', string='Daily Mail Template')
    sh_cust_week_day = fields.Selection([('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'), (
        '3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday')], string=' Week Day')
    sh_cust_weekly_statement_template_id = fields.Many2one(
        'mail.template', string='Weekly Mail Template')
    sh_cust_monthly_date = fields.Integer('Monthly Day',default=1)
    sh_cust_monthly_end = fields.Boolean('End of month')
    sh_cust_monthly_template_id = fields.Many2one(
        'mail.template', string='Monthly Mail Template')
    sh_cust_yearly_date = fields.Integer('Yearly day ',default=1)
    sh_cust_yearly_month = fields.Selection([
        ('january', 'January'),
        ('february', 'February'),
        ('march', 'March'),
        ('april', 'April'),
        ('may', 'May'),
        ('june', 'June'),
        ('july', 'July'),
        ('august', 'August'),
        ('september', 'September'),
        ('october', 'October'),
        ('november', 'November'),
        ('december', 'December')
    ], string='Month')
    sh_cust_yearly_template_id = fields.Many2one(
        'mail.template', string='  Yearly Mail Template')
    sh_cust_create_log_history = fields.Boolean(
        'Customer Statement Mail Log History')

    sh_customer_due_statement_auto_send = fields.Boolean(
        'Customer Overdue Statement Auto Send')
    sh_customer_due_statement_action = fields.Selection([('daily', 'Daily'), ('weekly', 'Weekly'), (
        'monthly', 'Monthly'), ('yearly', 'Yearly')], string='Customer Overdue Statement Action')
    sh_cus_due_daily_statement_template_id = fields.Many2one(
        'mail.template', string='Daily Mail Template ')
    sh_cust_due_week_day = fields.Selection([('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'), (
        '3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday')], string='  Week Day ')
    sh_cust_due_weekly_statement_template_id = fields.Many2one(
        'mail.template', string='Weekly Mail Template ')
    sh_cust_due_monthly_date = fields.Integer('Monthly Day ',default=1)
    sh_cust_due_monthly_end = fields.Boolean('End of month ')
    sh_cust_due_monthly_template_id = fields.Many2one(
        'mail.template', string='Monthly Mail Template ')
    sh_cust_due_yearly_date = fields.Integer('Yearly Day ',default=1)
    sh_cust_due_yearly_month = fields.Selection([
        ('january', 'January'),
        ('february', 'February'),
        ('march', 'March'),
        ('april', 'April'),
        ('may', 'May'),
        ('june', 'June'),
        ('july', 'July'),
        ('august', 'August'),
        ('september', 'September'),
        ('october', 'October'),
        ('november', 'November'),
        ('december', 'December')
    ], string=' Month')
    sh_cust_due_yearly_template_id = fields.Many2one(
        'mail.template', string=' Yearly Mail Template')
    sh_cust_due_create_log_history = fields.Boolean(
        'Customer Overdue Statement Mail Log History')

    sh_display_customer_statement = fields.Boolean('Show Customer Statement Menu in portal ?')
    sh_display_due_statement = fields.Selection([
        ('due','Only Due'),
        ('overdue','Only Overdue'),
        ('both','Both')
        ],string='Display Due/Overdue Statements',default='both',required=True)
    sh_statement_signature = fields.Boolean("Signature?", default=True)
    sh_display_message_in_chatter = fields.Boolean(
        "Display in Chatter Message?", default=True)
    sh_statement_pdf_in_message = fields.Boolean(
        "Send Report URL in Message?", default=True)
    sh_statement_url_in_message = fields.Boolean("Send Statement URL in Message?", default=True)
    sh_customer_statement_real_time_compute = fields.Boolean("Real-time Compute Statement in List, Kanban and Form View", default=True)
