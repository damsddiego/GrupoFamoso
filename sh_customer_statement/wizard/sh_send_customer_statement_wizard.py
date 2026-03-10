# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ShSendCustomerStatementWizard(models.TransientModel):
    _name = 'sh.send.customer.statement.wizard'
    _description = 'Send Customer Statement Wizard'

    start_date = fields.Date(string="Start Date", default=fields.Date.today)
    end_date = fields.Date(string="End Date", default=fields.Date.today)

    statement_type = fields.Selection([
        ('statement', 'Customer Statement'),
        ('overdue', 'Overdue Statement')
    ], string="Report Type", default='statement')

    is_show_aging_bucket = fields.Boolean(string="Show Aging Bucket", default=True)

    def _prepare_partners(self):
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            return False
        partners = self.env['res.partner'].browse(active_ids)

        return partners

    def action_send_statement(self):
        partners = self._prepare_partners()
        if not partners:
            return

        for partner in partners:
            partner.write({
                'start_date': self.start_date,
                'end_date': self.end_date,
            })
            partner.with_context(compute_statement=True)._compute_customer_statements()
            if self.statement_type == 'statement':
                partner.with_context(is_show_aging_bucket=self.is_show_aging_bucket, sh_hide_dates=False).action_send_customer_statement()
            else:
                partner.with_context(sh_hide_dates=False).action_send_customer_due_statement()
        return {'type': 'ir.actions.act_window_close'}

    def action_pdf(self):
        partners = self._prepare_partners()
        if not partners: return

        for partner in partners:
            partner.write({
                'start_date': self.start_date,
                'end_date': self.end_date,
            })
            partner.with_context(compute_statement=True)._compute_customer_statements()

        if self.statement_type == 'statement':
            return self.env.ref("sh_customer_statement.action_report_sh_customer_statement").with_context(sh_hide_dates=False, is_show_aging_bucket=self.is_show_aging_bucket).report_action(partners)
        else:
            return self.env.ref("sh_customer_statement.action_report_sh_customer_due_statement").with_context(sh_hide_dates=False).report_action(partners)

    def action_excel(self):
        partners = self._prepare_partners()
        if not partners: return

        for partner in partners:
            partner.write({
                'start_date': self.start_date,
                'end_date': self.end_date,
            })
            partner.with_context(compute_statement=True)._compute_customer_statements()

        if self.statement_type == 'statement':
            return partners[0].with_context(sh_hide_dates=False, is_show_aging_bucket=self.is_show_aging_bucket).action_print_customer_statement_xls()
        else:
            return partners[0].with_context(sh_hide_dates=False).action_print_customer_due_statement_xls()