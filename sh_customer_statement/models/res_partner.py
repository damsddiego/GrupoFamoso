# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from datetime import timedelta
from datetime import datetime
import calendar
import io
import pytz
import xlwt
import base64
import uuid
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError

_logger = logging.getLogger(__name__)
from datetime import date,datetime
from dateutil.relativedelta import relativedelta

PAYMENT_STATE_SELECTION = [
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
]

class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def default_start_date(self):
        return datetime.now().date().replace(month=1, day=1)

    @api.model
    def default_end_date(self):
        return fields.Date.today()

    start_date = fields.Date(default=default_start_date)
    end_date = fields.Date(default=default_end_date)
    sh_date_filter = fields.Selection([
        ('this_month','This Month'),
        ('last_month','Last Month'),
        ('this_quarter','This Quarter'),
        ('last_quarter','Last Quarter'),
        ('this_year','This Year'),
        ('last_year','Last Year'),
        ('custom','Custom'),
    ])


    sh_filter_customer_statement_ids = fields.One2many(
        "sh.res.partner.filter.statement",
        "partner_id",
        string="Customer Filtered Statements",
    )
    sh_customer_statement_ids = fields.One2many(
        "sh.customer.statement", "partner_id", string="Customer Statements"
    )
    sh_customer_zero_to_thiry = fields.Float("0-30")
    sh_customer_thirty_to_sixty = fields.Float("30-60")
    sh_customer_sixty_to_ninety = fields.Float("60-90")
    sh_customer_ninety_plus = fields.Float("90+")
    sh_customer_total = fields.Float("Total")

    sh_dont_send_customer_statement_auto = fields.Boolean("Don't send statement auto ?")
    sh_dont_send_due_customer_statement_auto = fields.Boolean(
        "Don't send Overdue statement auto ?"
    )
    sh_customer_due_statement_ids = fields.One2many(
        "sh.customer.due.statement", "partner_id", string="Customer Overdue Statements"
    )
    sh_customer_compute_boolean = fields.Boolean(
        "Boolean", compute="_compute_customer_statements"
    )
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    sh_cfs_statement_report_url = fields.Char(compute="_compute_cfs_report_url")
    sh_cust_statement_report_url = fields.Char(compute="_compute_cust_report_url")
    sh_cust_due_statement_report_url = fields.Char(
        compute="_compute_cust_due_report_url"
    )
    report_token = fields.Char("Access Token")
    portal_statement_url_wp = fields.Char(compute="_compute_statement_portal_url_wp")

    sh_customer_statement_config = fields.Many2many(
        "sh.customer.statement.config",
        string="Customer Statement Config",
        readonly=True,
    )
    payment_state = fields.Selection(PAYMENT_STATE_SELECTION, string="Payment Status")


    sh_customer_zero_to_thiry_adv = fields.Float("0-30")
    sh_customer_thirty_to_sixty_adv = fields.Float("30-60")
    sh_customer_sixty_to_ninety_adv = fields.Float("60-90")
    sh_customer_ninety_plus_adv = fields.Float("90+")
    sh_customer_total_adv = fields.Float("Total")

    def get_company(self):
        for rec in self:
            if rec.company_id:
                company=rec.company_id
            elif self._context and self._context.get('allowed_company_ids'):
                company= self.env['res.company'].search([('id','in',self._context.get('allowed_company_ids'))],limit=1)
            elif self.env.user and self.env.user.company_ids:
                company=self.env.user.company_ids[0]
            return company

    def _compute_statement_portal_url_wp(self):
        for rec in self:
            rec.portal_statement_url_wp = False
            if rec.company_id:
                company=rec.company_id
            elif self._context and self._context.get('allowed_company_ids'):
                company= self.env['res.company'].search([('id','in',self._context.get('allowed_company_ids'))],limit=1)

            if company and company.sh_statement_url_in_message:
                base_url = (
                    self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                )
                ticket_url = ""
                if rec.customer_rank > 0:
                    ticket_url = base_url + "/my/customer_statements"
                rec.portal_statement_url_wp = ticket_url

    def _get_token(self):
        """Get the current record access token"""
        if self.report_token:
            return self.report_token
        else:
            report_token = str(uuid.uuid4())
            self.write({"report_token": report_token})
            return report_token

    def get_download_report_url(self):
        url = ""
        if self.id:
            self.ensure_one()
            url = "/download/cfs/" + "%s?access_token=%s" % (self.id, self._get_token())
        return url

    def get_cust_statement_download_report_url(self):
        url = ""
        if self.id:
            self.ensure_one()
            url = "/download/cs/" + "%s?access_token=%s" % (self.id, self._get_token())
        return url

    def get_cust_due_statement_download_report_url(self):
        url = ""
        if self.id:
            self.ensure_one()
            url = "/download/cds/" + "%s?access_token=%s" % (self.id, self._get_token())
        return url

    def _compute_cfs_report_url(self):
        for rec in self:
            rec.sh_cfs_statement_report_url = False
            if rec.company_id:
                company=rec.company_id
            elif self._context and self._context.get('allowed_company_ids'):
                company= self.env['res.company'].search([('id','in',self._context.get('allowed_company_ids'))],limit=1)

            if company and company.sh_statement_pdf_in_message:
                base_url = (
                    self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                )
                if rec.customer_rank > 0:
                    rec.sh_cfs_statement_report_url = (
                        base_url + rec.get_download_report_url()
                    )

    def _compute_cust_report_url(self):
        for rec in self:
            rec.sh_cust_statement_report_url = False
            if rec.company_id:
                company=rec.company_id
            elif self._context and self._context.get('allowed_company_ids'):
                company= self.env['res.company'].search([('id','in',self._context.get('allowed_company_ids'))],limit=1)

            if company and company.sh_statement_pdf_in_message:
                base_url = (
                    self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                )
                if rec.customer_rank > 0:
                    rec.sh_cust_statement_report_url = (
                        base_url + rec.get_cust_statement_download_report_url()
                    )

    def _compute_cust_due_report_url(self):
        for rec in self:
            rec.sh_cust_due_statement_report_url = False
            if rec.company_id:
                company=rec.company_id
            elif self._context and self._context.get('allowed_company_ids'):
                company= self.env['res.company'].search([('id','in',self._context.get('allowed_company_ids'))],limit=1)
            if company and company.sh_statement_pdf_in_message:
                base_url = (
                    self.env["ir.config_parameter"].sudo().get_param("web.base.url")
                )
                if rec.customer_rank > 0:
                    rec.sh_cust_due_statement_report_url = (
                        base_url + rec.get_cust_due_statement_download_report_url()
                    )

    def _get_cfs_report_base_filename(self):
        self.ensure_one()
        return "%s %s" % ("Customer Statement Filter By Date", self.name)

    def _get_cs_report_base_filename(self):
        self.ensure_one()
        return "%s %s" % ("Customer Statement", self.name)

    def _get_cds_report_base_filename(self):
        self.ensure_one()
        return "%s %s" % ("Customer Due/Overdue Statement", self.name)

    def action_send_filter_customer_whatsapp(self):
        self.ensure_one()
        if not self.mobile:
            raise UserError(_("Partner Mobile Number Not Exist !"))
        template = self.env.ref(
            "sh_customer_statement.sh_send_customer_filter_whatsapp_email_template"
        )
        ctx = {
            "default_model": "res.partner",
            "default_res_ids": self.ids,
            "default_use_template": bool(template.id),
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "force_email": True,
            "default_is_customer_statement": True,
        }
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(False, "form")],
            "view_id": False,
            "target": "new",
            "context": ctx,
        }

    def action_send_customer_whatsapp(self):
        self.ensure_one()
        if not self.mobile:
            raise UserError(_("Partner Mobile Number Not Exist !"))
        template = self.env.ref(
            "sh_customer_statement.sh_send_customer_whatsapp_email_template"
        )
        ctx = {
            "default_model": "res.partner",
            "default_res_ids": self.ids,
            "default_use_template": bool(template.id),
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "force_email": True,
            "default_is_customer_statement": True,
        }
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(False, "form")],
            "view_id": False,
            "target": "new",
            "context": ctx,
        }

    def action_send_due_customer_whatsapp(self):
        self.ensure_one()
        if not self.mobile:
            raise UserError(_("Partner Mobile Number Not Exist !"))
        template = self.env.ref(
            "sh_customer_statement.sh_send_customer_due_whatsapp_email_template"
        )
        ctx = {
            "default_model": "res.partner",
            "default_res_ids": self.ids,
            "default_use_template": bool(template.id),
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "force_email": True,
            "default_is_customer_statement": True,
        }
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(False, "form")],
            "view_id": False,
            "target": "new",
            "context": ctx,
        }

    def update_statement_config_manually_(self):
        view = self.env.ref(
            "sh_customer_statement.sh_update_customers_statement_config_wizard"
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Mass Update Config",
            "view_mode": "form",
            "views": [(view.id, "form")],
            "res_model": "sh.customer.config.mass.update",
            "view_id": view.id,
            "target": "new",
            "context": {"default_sh_selected_partner_ids": self.ids},
        }

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        if self.filtered(lambda c: c.end_date and c.start_date and c.start_date > c.end_date):
            raise ValidationError(_("start date must be less than end date."))

    def _compute_customer_statements_old(self):
        # =====================================================================
        # ORIGINAL ORM METHOD (For Comparison)
        # =====================================================================
        company_ids=[]
        if self.env.context and self.env.context.get('allowed_company_ids'):
            company_ids=self.env.context.get('allowed_company_ids')
        elif self.env.context and self.env.context.get('uid'):
            current_user=self.env['res.users'].browse(self.env.context.get('uid'))
            if current_user:
                company_ids=current_user.company_ids.ids
        for rec in self:
            rec.sh_customer_compute_boolean=True
            rec.sh_customer_statement_ids=[(6,0,[])]
            rec.sh_customer_due_statement_ids=[(6,0,[])]

            partner_list=[rec]
            all_statement_lines_vals = []
            if rec.company_type == 'company':
                if rec.child_ids:
                    partner_list.extend(rec.child_ids)

            invoice_due_amount_0_to_30_sum=0
            credit_note_due_amount_0_to_30_sum=0
            payment_due_amount_0_to_30_sum=0


            invoice_due_amount_30_to_60_sum=0
            credit_note_due_amount_30_to_60_sum=0
            payment_due_amount_30_to_60_sum=0

            invoice_due_amount_60_to_90_sum=0
            credit_note_due_amount_60_to_90_sum=0
            payment_due_amount_60_to_90_sum=0

            invoice_due_amount_90_plus_sum=0
            credit_note_due_amount_90_plus_sum=0
            payment_due_amount_90_plus_sum=0

            adv_payment_due_amount_0_to_30_sum = 0
            adv_payment_due_amount_30_to_60_sum = 0
            adv_payment_due_amount_60_to_90_sum = 0
            adv_payment_due_amount_90_plus_sum = 0

            considered_payment_ids = set()
            for partner in partner_list:

                # ================================================================================
                # PREAPRE DATA FOR CUSTOMER STATEMENT WHICH PARTNER HAS CUSTOMER RANK MORE THAN 0
                # ================================================================================

                if rec.customer_rank > 0:

                    # ------- GET DATA OF INVOICE AND CREDIT NOTE FOR CURRENT PARTNER ----------

                    self._cr.execute(""" select id from account_move where partner_id=%s and move_type in ('out_invoice','out_refund') and state not in ('draft','cancel') and company_id in %s  """,[partner.id,tuple(company_ids)])
                    c_moves_statements=self._cr.dictfetchall()
                    c_moves_statements=self.env['account.move'].browse([r['id'] for r in c_moves_statements])


                    # FIND PAYMENTS SETTLED AGAINST THIS INVOICE
    
                    # ------- CREATE CUSTOMER STATEMENT LINE FROM INVOICE ----------
                    for move in c_moves_statements.filtered(lambda i:i.move_type=='out_invoice'):
                        sh_customer_paid_amount = move.amount_total - move.amount_residual
                        

                        payments = move._get_reconciled_payments()
                        if payments:
                            matched_payment_ids = move.matched_payment_ids.filtered(lambda p: not p.move_id and p.state == 'paid')
                            payments = payments + matched_payment_ids
                            considered_payment_ids.update(payments.ids)
                        if not payments and sh_customer_paid_amount:
                            payments = move.matched_payment_ids.filtered(lambda p: not p.move_id and p.state == 'paid')
                            considered_payment_ids.update(payments.ids)
                    
                        last_payment = payments.sorted(lambda p: p.date)[-1] if payments else False
                        if sh_customer_paid_amount:
                            sh_customer_paid_amount = sum(payments.mapped('amount'))
                        payment_ref = last_payment.name if last_payment else False
                        payment_date = last_payment.date if last_payment else False
                        
                        # sh_customer_paid_amount already calculated above

                        statement_vals = {
                            "sh_account": partner.property_account_receivable_id.name,
                            "name": move.name,
                            "currency_id": move.currency_id.id,
                            "sh_customer_invoice_date": move.invoice_date,
                            "sh_customer_due_date": move.invoice_date_due,
                            "sh_customer_amount": move.amount_total,
                            "sh_customer_paid_amount": sh_customer_paid_amount,
                            # "sh_customer_balance":  move.amount_residual,
                            "sh_customer_balance": (move.amount_total - sh_customer_paid_amount) if move.amount_total < sh_customer_paid_amount else move.amount_residual,
                            "partner_id":rec.id,
                            "sh_total_balance": 0.0,
                            "sh_payment_reference": payment_ref if sh_customer_paid_amount else '',
                            "sh_payment_date": payment_date,
                        }
                        self.env['sh.customer.statement'].create(statement_vals)
                        all_statement_lines_vals.append(statement_vals)

                    # ------- CREATE CUSTOMER STATEMENT LINE FROM CREDIT NOTE AND MULTIPLE WITH -1 BECAUSE IT REVERSE OF INVOICE  ----------
                    for move in c_moves_statements.filtered(lambda i: i.move_type == 'out_refund'):
                        sh_customer_paid_amount = move.amount_total - move.amount_residual

                        payments = move._get_reconciled_payments()
                        if move.matched_payment_ids:
                            payments = payments | move.matched_payment_ids
                        
                        payment_ref = ""
                        payment_date = False
                        if payments:
                            matched_payment_ids = move.matched_payment_ids.filtered(lambda p: not p.move_id and p.state == 'paid')
                            payments = payments + matched_payment_ids
                            considered_payment_ids.update(payments.ids)
                        if not payments and sh_customer_paid_amount:
                            payments = move.matched_payment_ids.filtered(lambda p: not p.move_id and p.state == 'paid')
                            considered_payment_ids.update(payments.ids)

                        last_payment = payments.sorted(lambda p: p.date)[-1] if payments else False
                        if sh_customer_paid_amount:
                            sh_customer_paid_amount = sum(payments.mapped('amount')) if hasattr(payments, 'amount') else sh_customer_paid_amount
                        payment_ref = last_payment.name if last_payment else False
                        payment_date = last_payment.date if last_payment else False

                        statement_vals = {
                            "sh_account": partner.property_account_receivable_id.name,
                            "name": move.name,
                            "currency_id": move.currency_id.id,
                            "sh_customer_invoice_date": move.invoice_date,
                            "sh_customer_due_date": move.invoice_date_due,
                            "sh_customer_amount": move.amount_total * -1,
                            "sh_customer_paid_amount": sh_customer_paid_amount * -1,
                            "sh_customer_balance": ((move.amount_total - sh_customer_paid_amount) if move.amount_total < sh_customer_paid_amount else move.amount_residual) * -1,
                            "partner_id": rec.id,
                            "sh_total_balance": 0.0,
                            "sh_payment_reference": payment_ref if sh_customer_paid_amount else '',
                            "sh_payment_date": payment_date,
                        }
                        self.env['sh.customer.statement'].create(statement_vals)
                        all_statement_lines_vals.append(statement_vals)

                    # ================================================================================
                    # GET PAYMENT OF CURRENT PARTNER WHICH IS NOT FULLY RECONCILE AND CUSTOMER
                    # RECEVING PAYMENT AND VENDOR SENDED PAYMENT
                    # ================================================================================

                    self._cr.execute(""" select id from account_payment where partner_id=%s and is_reconciled=False and partner_type='customer'  """,[partner.id,])
                    customer_payment=self._cr.dictfetchall()
                    customer_payment=self.env['account.payment'].browse([r['id'] for r in customer_payment])

                    # ------- CREATE CUSTOMER STATEMENT LINE FROM CUSTOMER INBOUND (RECEVING) PAYMENT ----------
                    for payment in customer_payment.filtered(lambda i:i.payment_type=='inbound' and i.state=='paid' and i.company_id.id in company_ids and i.id not in considered_payment_ids):
                        domain = [
                            ('account_id.account_type', 'in',('asset_receivable', 'liability_payable')),
                            ('parent_state', '=', 'posted'),
                            ('payment_id', '=', payment.id),
                        ]
                        unpaid_move=self.env['account.move.line'].search(domain)
                        if unpaid_move:
                             unpaid_amount = sum(unpaid_move.mapped('amount_residual_currency'))
                        else:
                             # Fallback for payments without lines (proxy reconciliation)
                             applied_sum = sum(
                                (m.amount_total - m.amount_residual) * 
                                (payment.amount / sum(m.matched_payment_ids.mapped('amount')))
                                for m in payment.matched_move_ids
                             )
                             unpaid_amount = payment.amount - applied_sum
                        
                        if payment.currency_id.is_zero(unpaid_amount):
                            continue
                        statement_vals = {
                            "sh_account": partner.property_account_receivable_id.name,
                            "name": payment.name,
                            "currency_id": payment.currency_id.id,
                            "sh_customer_invoice_date": False,
                            "sh_customer_amount": 0,
                            "sh_customer_paid_amount": abs(unpaid_amount) ,
                            "sh_total_balance": 0.0,
                            "sh_customer_balance": -unpaid_amount if unpaid_amount > 0 else unpaid_amount,
                            "partner_id":rec.id,
                            "sh_payment_reference": payment.name,
                            "sh_payment_date": payment.date,
                        }
                        self.env['sh.customer.statement'].create(statement_vals)
                        all_statement_lines_vals.append(statement_vals)

                    # ------- CREATE CUSTOMER STATEMENT LINE FROM VENDOR OUTBOUND (SENDING) PAYMENT ----------
                    for payment in customer_payment.filtered(lambda i:i.payment_type=='outbound' and i.state=='paid' and i.company_id.id in company_ids and i.id not in considered_payment_ids):
                        domain = [
                            ('account_id.account_type', 'in',('asset_receivable', 'liability_payable')),
                            ('parent_state', '=', 'posted'),
                            ('payment_id', '=', payment.id),
                        ]
                        unpaid_move=self.env['account.move.line'].search(domain)
                        unpaid_amount=sum(unpaid_move.mapped('amount_residual_currency'))
                        if payment.currency_id.is_zero(unpaid_amount):
                            continue
                        statement_vals = {
                            "sh_account": partner.property_account_receivable_id.name,
                            "name": payment.name,
                            "currency_id": payment.currency_id.id,
                            "sh_customer_invoice_date": False,
                            "sh_customer_amount": 0,
                            "sh_customer_paid_amount": abs(unpaid_amount) ,
                            "sh_customer_balance": unpaid_amount ,
                            "partner_id":rec.id,
                            "sh_payment_reference": payment.name,
                            "sh_payment_date": payment.date,
                        }
                        self.env['sh.customer.statement'].create(statement_vals)
                        all_statement_lines_vals.append(statement_vals)

                    #  ==================================================================
                    #  CALCULATE AGING FROM INVOICE AND PAYMENT OF CUSTOMER
                    #  ==================================================================
                    current_date=date.today()

                    # --------- CALCULATE 0 TO 30 DAYS BALANCE AMOUNT -----------------

                    self._cr.execute(""" select id,amount_residual from account_move where partner_id=%s and move_type ='out_invoice' and invoice_date<=%s and  invoice_date>%s  and state not in ('draft','cancel') and company_id in %s """,[partner.id,current_date,current_date-timedelta(days=30),tuple(company_ids)])
                    invoice_due_amount_0_to_30=self._cr.dictfetchall()
                    invoice_due_amount_0_to_30=sum([sub['amount_residual'] for sub in invoice_due_amount_0_to_30 ])
                    invoice_due_amount_0_to_30_sum+=invoice_due_amount_0_to_30
                    self._cr.execute(""" select id,amount_residual from account_move where partner_id=%s and move_type ='out_refund' and invoice_date<=%s and  invoice_date>%s  and state not in ('draft','cancel') and company_id in %s """,[partner.id,current_date,current_date-timedelta(days=30),tuple(company_ids)])
                    credit_note_due_amount_0_to_30=self._cr.dictfetchall()
                    credit_note_due_amount_0_to_30=sum([sub['amount_residual'] for sub in credit_note_due_amount_0_to_30 ])
                    credit_note_due_amount_0_to_30_sum+=credit_note_due_amount_0_to_30
                    payment_0_to_30=customer_payment.filtered(lambda i:i.state=='paid' and i.date<=current_date and i.date>current_date-timedelta(days=30) and i.company_id.id in company_ids)
                    payment_due_amount_0_to_30=0
                    if payment_0_to_30:
                        self._cr.execute(""" select aml.id, aml.amount_residual_currency, aml.move_id from account_move_line aml inner join account_move am on am.id = aml.move_id where aml.account_id in (select id from account_account where account_type in ('asset_receivable','liability_payable')) and aml.parent_state='posted' and aml.payment_id in %s and am.move_type = 'out_invoice'  """,[tuple(payment_0_to_30.ids),])
                        payment_due_amount_0_to_30=self._cr.dictfetchall()
                        payment_due_amount_0_to_30=sum([sub['amount_residual_currency'] for sub in payment_due_amount_0_to_30 ])
                        payment_due_amount_0_to_30_sum+=payment_due_amount_0_to_30
                    rec.sh_customer_zero_to_thiry=invoice_due_amount_0_to_30_sum-credit_note_due_amount_0_to_30_sum+payment_due_amount_0_to_30_sum

                    # --------- CALCULATE 30 TO 60 DAYS BALANCE AMOUNT -----------------

                    self._cr.execute(""" select id,amount_residual from account_move where partner_id=%s and move_type ='out_invoice' and invoice_date<=%s and  invoice_date>%s  and state not in ('draft','cancel') and company_id in %s  """,[partner.id,current_date-timedelta(days=30),current_date-timedelta(days=60),tuple(company_ids)])
                    invoice_due_amount_30_to_60=self._cr.dictfetchall()
                    invoice_due_amount_30_to_60=sum([sub['amount_residual'] for sub in invoice_due_amount_30_to_60 ])
                    invoice_due_amount_30_to_60_sum+=invoice_due_amount_30_to_60
                    self._cr.execute(""" select id,amount_residual from account_move where partner_id=%s and move_type ='out_refund' and invoice_date<=%s and  invoice_date>%s  and state not in ('draft','cancel')  and company_id in %s """,[partner.id,current_date-timedelta(days=30),current_date-timedelta(days=60),tuple(company_ids)])
                    credit_note_due_amount_30_to_60=self._cr.dictfetchall()
                    credit_note_due_amount_30_to_60=sum([sub['amount_residual'] for sub in credit_note_due_amount_30_to_60 ])
                    credit_note_due_amount_30_to_60_sum+=credit_note_due_amount_30_to_60

                    payment_30_to_60=customer_payment.filtered(lambda i:i.state=='paid' and i.date<=current_date-timedelta(days=30) and i.date>current_date-timedelta(days=60) and i.company_id.id in company_ids)
                    payment_due_amount_30_to_60=0
                    if payment_30_to_60:
                        self._cr.execute(""" select aml.id, aml.amount_residual_currency, aml.move_id from account_move_line aml inner join account_move am on am.id = aml.move_id where aml.account_id in (select id from account_account where account_type in ('asset_receivable','liability_payable')) and aml.parent_state='posted' and aml.payment_id in %s and am.move_type = 'out_invoice'  """,[tuple(payment_30_to_60.ids),])
                        payment_due_amount_30_to_60=self._cr.dictfetchall()
                        payment_due_amount_30_to_60=sum([sub['amount_residual_currency'] for sub in payment_due_amount_30_to_60 ])
                        payment_due_amount_30_to_60_sum+=payment_due_amount_30_to_60
                    rec.sh_customer_thirty_to_sixty=invoice_due_amount_30_to_60_sum-credit_note_due_amount_30_to_60_sum+payment_due_amount_30_to_60_sum

                    # --------- CALCULATE 60 TO 90 DAYS BALANCE AMOUNT -----------------

                    self._cr.execute(""" select id,amount_residual from account_move where partner_id=%s and move_type ='out_invoice' and invoice_date<=%s and  invoice_date>%s  and state not in ('draft','cancel') and company_id in %s  """,[partner.id,current_date-timedelta(days=60),current_date-timedelta(days=90),tuple(company_ids)])
                    invoice_due_amount_60_to_90=self._cr.dictfetchall()
                    invoice_due_amount_60_to_90=sum([sub['amount_residual'] for sub in invoice_due_amount_60_to_90 ])
                    invoice_due_amount_60_to_90_sum+=invoice_due_amount_60_to_90
                    self._cr.execute(""" select id,amount_residual from account_move where partner_id=%s and move_type ='out_refund' and invoice_date<=%s and  invoice_date>%s  and state not in ('draft','cancel') and company_id in %s  """,[partner.id,current_date-timedelta(days=60),current_date-timedelta(days=90),tuple(company_ids)])
                    credit_note_due_amount_60_to_90=self._cr.dictfetchall()
                    credit_note_due_amount_60_to_90=sum([sub['amount_residual'] for sub in credit_note_due_amount_60_to_90 ])
                    credit_note_due_amount_60_to_90_sum+=credit_note_due_amount_60_to_90

                    payment_60_to_90=customer_payment.filtered(lambda i:i.state=='paid' and i.date<=current_date-timedelta(days=60) and i.date>current_date-timedelta(days=90) and i.company_id.id in company_ids)
                    payment_due_amount_60_to_90=0
                    if payment_60_to_90:
                        self._cr.execute(""" select aml.id, aml.amount_residual_currency, aml.move_id from account_move_line aml inner join account_move am on am.id = aml.move_id where aml.account_id in (select id from account_account where account_type in ('asset_receivable','liability_payable')) and aml.parent_state='posted' and aml.payment_id in %s and am.move_type = 'out_invoice'  """,[tuple(payment_60_to_90.ids),])
                        payment_due_amount_60_to_90=self._cr.dictfetchall()
                        payment_due_amount_60_to_90=sum([sub['amount_residual_currency'] for sub in payment_due_amount_60_to_90 ])
                        payment_due_amount_60_to_90_sum+=payment_due_amount_60_to_90
                    rec.sh_customer_sixty_to_ninety=invoice_due_amount_60_to_90_sum-credit_note_due_amount_60_to_90_sum+payment_due_amount_60_to_90_sum

                    # --------- CALCULATE 30 TO 60 DAYS BALANCE AMOUNT -----------------

                    self._cr.execute(""" select id,amount_residual from account_move where partner_id=%s and move_type ='out_invoice' and invoice_date<=%s  and state not in ('draft','cancel') and company_id in %s  """,[partner.id,current_date-timedelta(days=90),tuple(company_ids)])
                    invoice_due_amount_90_plus=self._cr.dictfetchall()
                    invoice_due_amount_90_plus=sum([sub['amount_residual'] for sub in invoice_due_amount_90_plus ])
                    invoice_due_amount_90_plus_sum+=invoice_due_amount_90_plus

                    self._cr.execute(""" select id,amount_residual from account_move where partner_id=%s and move_type ='out_refund' and invoice_date<=%s  and state not in ('draft','cancel') and company_id in %s  """,[partner.id,current_date-timedelta(days=90),tuple(company_ids)])
                    credit_note_due_amount_90_plus=self._cr.dictfetchall()
                    credit_note_due_amount_90_plus=sum([sub['amount_residual'] for sub in credit_note_due_amount_90_plus ])
                    credit_note_due_amount_90_plus_sum +=credit_note_due_amount_90_plus

                    payment_90_plus=customer_payment.filtered(lambda i:i.state=='paid' and i.date<=current_date-timedelta(days=90) and i.company_id.id in company_ids)
                    payment_due_amount_90_plus=0
                    if payment_90_plus:
                        self._cr.execute(""" select aml.id, aml.amount_residual_currency, aml.move_id from account_move_line aml inner join account_move am on am.id = aml.move_id where aml.account_id in (select id from account_account where account_type in ('asset_receivable','liability_payable')) and aml.parent_state='posted' and aml.payment_id in %s and am.move_type = 'out_invoice'  """,[tuple(payment_90_plus.ids),])
                        payment_due_amount_90_plus=self._cr.dictfetchall()
                        payment_due_amount_90_plus=sum([sub['amount_residual_currency'] for sub in payment_due_amount_90_plus ])
                        payment_due_amount_90_plus_sum+=payment_due_amount_90_plus
                    rec.sh_customer_ninety_plus=invoice_due_amount_90_plus_sum-credit_note_due_amount_90_plus_sum+payment_due_amount_90_plus_sum

                    rec.sh_customer_total=rec.sh_customer_zero_to_thiry+rec.sh_customer_thirty_to_sixty+rec.sh_customer_sixty_to_ninety+rec.sh_customer_ninety_plus

                    #  ==================================================================
                    #  CALCULATE AGING FOR ADVANCE PAYMENT OF CUSTOMER
                    #  ==================================================================
                    current_date=date.today()

                    adv_payment_due_amount_0_to_30_sum = 0
                    adv_payment_due_amount_30_to_60_sum = 0
                    adv_payment_due_amount_60_to_90_sum = 0
                    adv_payment_due_amount_90_plus_sum = 0

                    for vals in all_statement_lines_vals:
                        if vals.get('sh_customer_balance', 0) < 0:
                            line_date = vals.get('sh_customer_invoice_date') or vals.get('sh_payment_date')
                            if not line_date:
                                continue
                            if isinstance(line_date, str):
                                line_date = fields.Date.from_string(line_date)

                            delta = (current_date - line_date).days
                            if delta < 30:
                                adv_payment_due_amount_0_to_30_sum += vals.get('sh_customer_balance')
                            elif delta < 60:
                                adv_payment_due_amount_30_to_60_sum += vals.get('sh_customer_balance')
                            elif delta < 90:
                                adv_payment_due_amount_60_to_90_sum += vals.get('sh_customer_balance')
                            else:
                                adv_payment_due_amount_90_plus_sum += vals.get('sh_customer_balance')

                    rec.sh_customer_zero_to_thiry_adv = abs(adv_payment_due_amount_0_to_30_sum)
                    rec.sh_customer_thirty_to_sixty_adv = abs(adv_payment_due_amount_30_to_60_sum)
                    rec.sh_customer_sixty_to_ninety_adv = abs(adv_payment_due_amount_60_to_90_sum)
                    rec.sh_customer_ninety_plus_adv = abs(adv_payment_due_amount_90_plus_sum)
                    rec.sh_customer_total_adv = rec.sh_customer_zero_to_thiry_adv + rec.sh_customer_thirty_to_sixty_adv + rec.sh_customer_sixty_to_ninety_adv + rec.sh_customer_ninety_plus_adv


                    #  ==================================================================
                    #  OVERDUE STATEMENT LINE CREATE ACCORDING TO CONFIGURATION IN
                    #  ==================================================================
                    due_invoices=False
                    if self.env.company.sh_display_due_statement =='due':
                        due_invoices=c_moves_statements.filtered(lambda x:x.amount_residual>0 and x.invoice_date_due >= current_date  )

                    elif self.env.company.sh_display_due_statement =='overdue':
                        due_invoices=c_moves_statements.filtered(lambda x:x.amount_residual>0 and x.invoice_date_due < current_date  )
                    elif self.env.company.sh_display_due_statement =='both':
                        due_invoices=c_moves_statements.filtered(lambda x:x.amount_residual>0 )
                    if due_invoices:
                        for invoice in due_invoices.filtered(lambda i: i.move_type == 'out_invoice'):
                            payments = invoice._get_reconciled_payments()
                            if payments:
                                considered_payment_ids.update(payments.ids)

                            overdue_statement_vals = {
                                "sh_account": partner.property_account_receivable_id.name,
                                "currency_id": invoice.currency_id.id,
                                "name": invoice.name,
                                "sh_today": current_date,
                                "sh_due_customer_invoice_date": invoice.invoice_date,
                                "sh_due_customer_due_date": invoice.invoice_date_due,
                                "partner_id": rec.id,
                                "sh_due_customer_amount": invoice.amount_total,
                                "sh_due_customer_paid_amount": invoice.amount_total - invoice.amount_residual,
                                "sh_due_customer_balance": invoice.amount_residual,
                            }
                            self.env['sh.customer.due.statement'].create(overdue_statement_vals)


                        # ------- CREATE CUSTOMER STATEMENT LINE FROM CREDIT NOTE AND MULTIPLE WITH -1 BECAUSE IT REVERSE OF INVOICE  ----------
                        for invoice in due_invoices.filtered(lambda i: i.move_type == 'out_refund'):
                            payments = invoice._get_reconciled_payments()
                            if payments:
                                considered_payment_ids.update(payments.ids)

                            overdue_statement_vals = {
                                "sh_account": partner.property_account_receivable_id.name,
                                "currency_id": invoice.currency_id.id,
                                "name": invoice.name,
                                "sh_today": current_date,
                                "sh_due_customer_invoice_date": invoice.invoice_date,
                                "sh_due_customer_due_date": invoice.invoice_date_due,
                                "partner_id": rec.id,
                                "sh_due_customer_amount": invoice.amount_total * -1,
                                "sh_due_customer_paid_amount": (invoice.amount_total - invoice.amount_residual) * -1,
                                "sh_due_customer_balance": invoice.amount_residual * -1,
                            }
                            self.env['sh.customer.due.statement'].create(overdue_statement_vals)


                    # ============================
                    # CALCULATE TOTAL BALANCE
                    all_lines = rec.sh_customer_statement_ids.sorted(key=lambda x: x.id)

                    running_total = 0.0
                    for line in all_lines:
                        # Always use the balance value stored while creating the line
                        line_balance = line.sh_customer_balance

                        running_total += line_balance
                        line.sh_total_balance = running_total

    def sh_compute_action(self):
        for rec in self:
            rec.with_context(compute_statement=True)._compute_customer_statements()

    def _compute_customer_statements(self):
        # We use logic from _compute_customer_statements_old but implementation in SQL and update changes so both are not same method
        # _compute_customer_statements update method.
        
        context = dict(self.env.context or {})
        if not context.get('compute_statement', False): 
            if not self.env.company.sh_customer_statement_real_time_compute:
                for rec in self:
                    rec.sh_customer_compute_boolean = False
                return
        company_ids = self.env.context.get('allowed_company_ids') or self.env.company.ids
        if not company_ids:
            if self.env.user and self.env.user.company_ids:
                company_ids = self.env.user.company_ids.ids
        
        self.env.flush_all()
        current_date = date.today()
        
        for rec in self:
            rec.sh_customer_compute_boolean = True
            
            # Clear existing statement data
            self._cr.execute("DELETE FROM sh_customer_statement WHERE partner_id = %s", [rec.id])
            self._cr.execute("DELETE FROM sh_customer_due_statement WHERE partner_id = %s", [rec.id])
            
            # Get IDs for the partner and its children
            partner_ids = [rec.id]
            if rec.company_type == 'company':
                partner_ids.extend(rec.child_ids.ids)
            
            if rec.customer_rank > 0:
                # 1. Insert Invoices and Credit Notes
                # We also attempt to find the last payment reference/date as per _old logic
                sql_insert_moves = """
                    INSERT INTO sh_customer_statement (
                        partner_id, currency_id, name, sh_account, 
                        sh_customer_invoice_date, sh_customer_due_date, 
                        sh_customer_amount, sh_customer_paid_amount, 
                        sh_customer_balance, sh_payment_reference, sh_payment_date,
                        create_uid, create_date, write_uid, write_date
                    )
                    SELECT 
                        %s, m.currency_id, m.name, COALESCE(a.name->>'en_US', a.name::text), 
                        m.invoice_date, m.invoice_date_due,
                        CASE WHEN m.move_type = 'out_invoice' THEN m.amount_total ELSE m.amount_total * -1 END,
                        CASE WHEN m.move_type = 'out_invoice' THEN (m.amount_total - m.amount_residual) ELSE (m.amount_total - m.amount_residual) * -1 END,
                        CASE WHEN m.move_type = 'out_invoice' THEN m.amount_residual ELSE m.amount_residual * -1 END,
                        COALESCE(sub_pay.payment_ref, sub_move.move_ref),
                        COALESCE(sub_pay.payment_date, sub_move.move_date),
                        %s, NOW(), %s, NOW()
                    FROM account_move m
                    LEFT JOIN LATERAL (
                        SELECT l.account_id 
                        FROM account_move_line l
                        JOIN account_account acc ON acc.id = l.account_id
                        WHERE l.move_id = m.id AND acc.account_type = 'asset_receivable'
                        LIMIT 1
                    ) aml ON TRUE
                    LEFT JOIN account_account a ON a.id = aml.account_id
                    LEFT JOIN LATERAL (
                        SELECT 
                            string_agg(DISTINCT ap.name, ', ' ORDER BY ap.name) as payment_ref,
                            MAX(ap.date) as payment_date
                        FROM (
                            SELECT payment_line.payment_id as id FROM account_partial_reconcile apr 
                            JOIN account_move_line invoice_line ON (invoice_line.id = apr.credit_move_id OR invoice_line.id = apr.debit_move_id)
                            JOIN account_move_line payment_line ON (payment_line.id = apr.credit_move_id OR payment_line.id = apr.debit_move_id)
                            WHERE invoice_line.move_id = m.id AND payment_line.payment_id IS NOT NULL
                            UNION
                            SELECT payment_id FROM account_move__account_payment WHERE invoice_id = m.id
                        ) sub_p
                        JOIN account_payment ap ON ap.id = sub_p.id
                    ) sub_pay ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT 
                            string_agg(DISTINCT pm.name, ', ' ORDER BY pm.name) as move_ref,
                            MAX(pm.date) as move_date
                        FROM account_partial_reconcile apr 
                        JOIN account_move_line invoice_line ON (invoice_line.id = apr.credit_move_id OR invoice_line.id = apr.debit_move_id)
                        JOIN account_move_line payment_line ON (payment_line.id = apr.credit_move_id OR payment_line.id = apr.debit_move_id)
                        JOIN account_move pm ON pm.id = payment_line.move_id
                        WHERE invoice_line.move_id = m.id AND payment_line.move_id != m.id
                    ) sub_move ON TRUE
                    WHERE m.partner_id IN %s 
                      AND m.move_type IN ('out_invoice', 'out_refund')
                      AND m.state NOT IN ('draft', 'cancel')
                      AND m.company_id IN %s
                """
                self._cr.execute(sql_insert_moves, [rec.id, self.env.uid, self.env.uid, tuple(partner_ids), tuple(company_ids)])

                # 2. Insert Unreconciled Payments
                sql_insert_payments = """
                    INSERT INTO sh_customer_statement (
                        partner_id, currency_id, name, sh_account, 
                        sh_customer_invoice_date, sh_customer_due_date, sh_customer_amount, 
                        sh_customer_paid_amount, sh_customer_balance, 
                        sh_payment_reference, sh_payment_date,
                        create_uid, create_date, write_uid, write_date
                    )
                    SELECT 
                        %s, p.currency_id, p.name, COALESCE(a.name->>'en_US', a.name::text), 
                        NULL, NULL, 0.0,
                        ABS(COALESCE(SUM(l.amount_residual_currency), p.amount - COALESCE(sub_applied.applied_amount, 0.0))),
                        CASE WHEN p.payment_type = 'inbound' THEN -1.0 ELSE 1.0 END * ABS(COALESCE(SUM(l.amount_residual_currency), p.amount - COALESCE(sub_applied.applied_amount, 0.0))),
                        p.name, p.date,
                        %s, NOW(), %s, NOW()
                    FROM account_payment p
                    LEFT JOIN account_account a ON a.id = p.destination_account_id
                    LEFT JOIN account_move_line l ON l.payment_id = p.id AND l.account_id IN (
                        SELECT id FROM account_account WHERE account_type IN ('asset_receivable', 'liability_payable')
                    ) AND l.parent_state = 'posted'
                    LEFT JOIN LATERAL (
                        SELECT SUM(
                            (m.amount_total - m.amount_residual) * 
                            (p.amount / NULLIF((SELECT SUM(ap_inner.amount) 
                                                FROM account_payment ap_inner 
                                                JOIN account_move__account_payment link_inner ON link_inner.payment_id = ap_inner.id 
                                                WHERE link_inner.invoice_id = m.id), 0))
                        ) as applied_amount
                        FROM account_move m
                        JOIN account_move__account_payment link ON link.invoice_id = m.id
                        WHERE link.payment_id = p.id
                    ) sub_applied ON TRUE
                    WHERE p.partner_id IN %s 
                      AND p.is_reconciled = False 
                      AND p.partner_type = 'customer'
                      AND p.state = 'paid'
                      AND p.company_id IN %s
                    GROUP BY p.id, p.currency_id, p.name, a.name, p.date, p.amount, p.partner_id, p.payment_type, sub_applied.applied_amount
                    HAVING ROUND(COALESCE(SUM(l.amount_residual_currency), p.amount - COALESCE(sub_applied.applied_amount, 0.0)), 2) != 0
                """
                self._cr.execute(sql_insert_payments, [rec.id, self.env.uid, self.env.uid, tuple(partner_ids), tuple(company_ids)])

                # 3. Calculate Aging Buckets (Standard: Invoices and Credit Notes)
                aging_sql = """
                    SELECT 
                        SUM(CASE WHEN invoice_date <= %s AND invoice_date > %s - INTERVAL '30 days' THEN balance ELSE 0 END) as bucket_0_30,
                        SUM(CASE WHEN invoice_date <= %s - INTERVAL '30 days' AND invoice_date > %s - INTERVAL '60 days' THEN balance ELSE 0 END) as bucket_31_60,
                        SUM(CASE WHEN invoice_date <= %s - INTERVAL '60 days' AND invoice_date > %s - INTERVAL '90 days' THEN balance ELSE 0 END) as bucket_61_90,
                        SUM(CASE WHEN invoice_date <= %s - INTERVAL '90 days' THEN balance ELSE 0 END) as bucket_91_plus
                    FROM (
                        SELECT invoice_date, amount_residual as balance FROM account_move 
                        WHERE partner_id IN %s AND move_type = 'out_invoice' AND state NOT IN ('draft', 'cancel') AND company_id IN %s
                        UNION ALL
                        SELECT invoice_date, -amount_residual as balance FROM account_move 
                        WHERE partner_id IN %s AND move_type = 'out_refund' AND state NOT IN ('draft', 'cancel') AND company_id IN %s
                    ) as combined_data
                """
                self._cr.execute(aging_sql, [current_date, current_date, current_date, current_date, current_date, current_date, current_date, tuple(partner_ids), tuple(company_ids), tuple(partner_ids), tuple(company_ids)])
                aging_res = self._cr.dictfetchone() or {}

                # 4. ADVANCE Aging Buckets (All credits: Unapplied Payments and Credit Notes)
                adv_aging_sql = """
                    SELECT 
                        SUM(CASE WHEN date <= %s AND date > %s - INTERVAL '30 days' THEN balance ELSE 0 END) as adv_bucket_0_30,
                        SUM(CASE WHEN date <= %s - INTERVAL '30 days' AND date > %s - INTERVAL '60 days' THEN balance ELSE 0 END) as adv_bucket_31_60,
                        SUM(CASE WHEN date <= %s - INTERVAL '60 days' AND date > %s - INTERVAL '90 days' THEN balance ELSE 0 END) as adv_bucket_61_90,
                        SUM(CASE WHEN date <= %s - INTERVAL '90 days' THEN balance ELSE 0 END) as adv_bucket_91_plus
                    FROM (
                        -- Unapplied Payments
                        SELECT 
                            p.date as date, 
                            ABS(COALESCE(SUM(l.amount_residual_currency), p.amount - COALESCE(sub_applied.applied_amount, 0.0))) as balance
                        FROM account_payment p
                        LEFT JOIN account_move_line l ON l.payment_id = p.id AND l.account_id IN (
                            SELECT id FROM account_account WHERE account_type IN ('asset_receivable', 'liability_payable')
                        ) AND l.parent_state = 'posted'
                        LEFT JOIN LATERAL (
                            SELECT SUM(
                                (m.amount_total - m.amount_residual) * 
                                (p.amount / NULLIF((SELECT SUM(ap_inner.amount) 
                                                    FROM account_payment ap_inner 
                                                    JOIN account_move__account_payment link_inner ON link_inner.payment_id = ap_inner.id 
                                                    WHERE link_inner.invoice_id = m.id), 0))
                            ) as applied_amount
                            FROM account_move m
                            JOIN account_move__account_payment link ON link.invoice_id = m.id
                            WHERE link.payment_id = p.id
                        ) sub_applied ON TRUE
                        WHERE p.partner_id IN %s AND p.is_reconciled = False AND p.partner_type = 'customer' AND p.state = 'paid' AND p.company_id IN %s
                        AND p.payment_type = 'inbound'
                        GROUP BY p.id, p.date, p.amount, sub_applied.applied_amount
                        HAVING ROUND(COALESCE(SUM(l.amount_residual_currency), p.amount - COALESCE(sub_applied.applied_amount, 0.0)), 2) != 0
                        
                        UNION ALL
                        
                        -- Unapplied Credit Notes (All credit notes are basically potential advances if unapplied)
                        SELECT invoice_date as date, amount_residual as balance FROM account_move
                        WHERE partner_id IN %s AND move_type = 'out_refund' AND state NOT IN ('draft', 'cancel') AND company_id IN %s
                        AND amount_residual > 0
                    ) as combined_adv
                """
                self._cr.execute(adv_aging_sql, [current_date, current_date, current_date, current_date, current_date, current_date, current_date, tuple(partner_ids), tuple(company_ids), tuple(partner_ids), tuple(company_ids)])
                adv_aging_res = self._cr.dictfetchone() or {}

                # Update Partner fields
                aging_bucket_0_30 = aging_res.get('bucket_0_30') or 0.0
                aging_bucket_31_60 = aging_res.get('bucket_31_60') or 0.0
                aging_bucket_61_90 = aging_res.get('bucket_61_90') or 0.0
                aging_bucket_91_plus = aging_res.get('bucket_91_plus') or 0.0
                total = aging_bucket_0_30 + aging_bucket_31_60 + aging_bucket_61_90 + aging_bucket_91_plus
                
                adv_bucket_0_30 = (adv_aging_res.get('adv_bucket_0_30') or 0.0)
                adv_bucket_31_60 = (adv_aging_res.get('adv_bucket_31_60') or 0.0)
                adv_bucket_61_90 = (adv_aging_res.get('adv_bucket_61_90') or 0.0)
                adv_bucket_91_plus = (adv_aging_res.get('adv_bucket_91_plus') or 0.0)
                total_adv = adv_bucket_0_30 + adv_bucket_31_60 + adv_bucket_61_90 + adv_bucket_91_plus
                
                update_partner_sql = """
                    UPDATE res_partner SET 
                        sh_customer_zero_to_thiry = %s,
                        sh_customer_thirty_to_sixty = %s,
                        sh_customer_sixty_to_ninety = %s,
                        sh_customer_ninety_plus = %s,
                        sh_customer_total = %s,
                        sh_customer_zero_to_thiry_adv = %s,
                        sh_customer_thirty_to_sixty_adv = %s,
                        sh_customer_sixty_to_ninety_adv = %s,
                        sh_customer_ninety_plus_adv = %s,
                        sh_customer_total_adv = %s
                    WHERE id = %s
                """
                self._cr.execute(update_partner_sql, [
                    aging_bucket_0_30, aging_bucket_31_60, 
                    aging_bucket_61_90, aging_bucket_91_plus, total,
                    adv_bucket_0_30, adv_bucket_31_60,
                    adv_bucket_61_90, adv_bucket_91_plus, 
                    total_adv, rec.id
                ])

                # 5. Overdue statements
                display_conf = self.env.company.sh_display_due_statement
                due_filter = ""
                if display_conf == 'due':
                    due_filter = "AND m.invoice_date_due >= CURRENT_DATE"
                elif display_conf == 'overdue':
                    due_filter = "AND m.invoice_date_due < CURRENT_DATE"
                
                if display_conf in ['due', 'overdue', 'both']:
                    sql_overdue = f"""
                        INSERT INTO sh_customer_due_statement (
                            partner_id, currency_id, name, sh_account, sh_today,
                            sh_due_customer_invoice_date, sh_due_customer_due_date,
                            sh_due_customer_amount, sh_due_customer_paid_amount, sh_due_customer_balance,
                            create_uid, create_date, write_uid, write_date
                        )
                        SELECT 
                            %s, m.currency_id, m.name, COALESCE(a.name->>'en_US', a.name::text), CURRENT_DATE,
                            m.invoice_date, m.invoice_date_due,
                            CASE WHEN m.move_type = 'out_invoice' THEN m.amount_total ELSE m.amount_total * -1 END,
                            CASE WHEN m.move_type = 'out_invoice' THEN (m.amount_total - m.amount_residual) ELSE (m.amount_total - m.amount_residual) * -1 END,
                            CASE WHEN m.move_type = 'out_invoice' THEN m.amount_residual ELSE m.amount_residual * -1 END,
                            %s, NOW(), %s, NOW()
                        FROM account_move m
                        LEFT JOIN LATERAL (
                            SELECT l.account_id 
                            FROM account_move_line l
                            JOIN account_account acc ON acc.id = l.account_id
                            WHERE l.move_id = m.id AND acc.account_type = 'asset_receivable'
                            LIMIT 1
                        ) aml ON TRUE
                        LEFT JOIN account_account a ON a.id = aml.account_id
                        WHERE m.partner_id IN %s AND m.amount_residual > 0 
                          AND m.move_type IN ('out_invoice', 'out_refund')
                          AND m.state NOT IN ('draft', 'cancel') AND m.company_id IN %s
                          {due_filter}
                    """
                    self._cr.execute(sql_overdue, [rec.id, self.env.uid, self.env.uid, tuple(partner_ids), tuple(company_ids)])

            # Running total update for current partner's statement lines
            self._cr.execute("""
                WITH sorted_statements AS (
                    SELECT id, sh_customer_balance, 
                           SUM(sh_customer_balance) OVER (PARTITION BY partner_id ORDER BY sh_customer_invoice_date, id) as running_total
                    FROM sh_customer_statement
                    WHERE partner_id = %s
                )
                UPDATE sh_customer_statement s
                SET sh_total_balance = ss.running_total
                FROM sorted_statements ss
                WHERE s.id = ss.id
            """, [rec.id])
            
            rec.invalidate_recordset([
                'sh_customer_statement_ids', 'sh_customer_due_statement_ids',
                'sh_customer_zero_to_thiry', 'sh_customer_thirty_to_sixty',
                'sh_customer_sixty_to_ninety', 'sh_customer_ninety_plus',
                'sh_customer_total', 'sh_customer_zero_to_thiry_adv',
                'sh_customer_thirty_to_sixty_adv', 'sh_customer_sixty_to_ninety_adv',
                'sh_customer_ninety_plus_adv', 'sh_customer_total_adv'
            ])



    def send_customer_statement(self):
        # This is called from the "Action" menu in list view
        view = self.env.ref("sh_customer_statement.sh_send_customer_statement_wizard_view_form")
        return {
            "type": "ir.actions.act_window",
            "name": "Send Customer Statement",
            "view_mode": "form",
            "res_model": "sh.send.customer.statement.wizard",
            "views": [(view.id, "form")],
            "target": "new",
            "context": {
                "default_statement_type": "statement",
                "active_ids": self.ids,
            },
        }

    def send_customer_overdue_statement(self):
        # Add this logic to handle mass overdue selection
        view = self.env.ref("sh_customer_statement.sh_send_customer_statement_wizard_view_form")
        return {
            "type": "ir.actions.act_window",
            "name": "Send Overdue Statement",
            "view_mode": "form",
            "res_model": "sh.send.customer.statement.wizard",
            "views": [(view.id, "form")],
            "target": "new",
            "context": {
                "default_statement_type": "overdue",
                "active_ids": self.ids,
            },
        }

    def action_print_customer_statement(self):
        return self.env.ref(
            "sh_customer_statement.action_report_sh_customer_statement"
        ).with_context(sh_hide_dates=True, always_show_bucket=True).report_action(self)

    def action_send_customer_statement(self):
        self.ensure_one()
        template = self.env.ref(
            "sh_customer_statement.sh_customer_statement_mail_template"
        )
        if template:
            mail = template.sudo().with_context(self.env.context, always_show_bucket=True).send_mail(self.id, force_send=True)
            mail_id = self.env["mail.mail"].sudo().browse(mail)
            if (mail_id and self.env.company.sh_cust_create_log_history):
                self.env["sh.customer.mail.history"].sudo().create(
                    {
                        "name": "Customer Account Statement",
                        "sh_statement_type": "customer_statement",
                        "sh_current_date": fields.Datetime.now(),
                        "sh_partner_id": self.id,
                        "sh_mail_id": mail_id.id,
                        "sh_mail_status": mail_id.state,
                    }
                )

    def action_print_customer_due_statement(self):
        return self.env.ref(
            "sh_customer_statement.action_report_sh_customer_due_statement"
        ).with_context(sh_hide_dates=True).report_action(self)

    def action_send_customer_due_statement(self):
        self.ensure_one()
        template = self.env.ref(
            "sh_customer_statement.sh_customer_due_statement_mail_template"
        )
        if template:
            mail = template.sudo().with_context(self.env.context).send_mail(self.id, force_send=True)
            mail_id = self.env["mail.mail"].sudo().browse(mail)
            if (mail_id and self.env.company.sh_cust_due_create_log_history):
                self.env["sh.customer.mail.history"].sudo().create(
                    {
                        "name": "Customer Account Overdue Statement",
                        "sh_statement_type": "customer_overdue_statement",
                        "sh_current_date": fields.Datetime.now(),
                        "sh_partner_id": self.id,
                        "sh_mail_id": mail_id.id,
                        "sh_mail_status": mail_id.state,
                    }
                )

    def action_get_customer_statement(self):
        self.ensure_one()
        today = date.today()
        currQuarter = int((today.month - 1) / 3 + 1)
        if self.sh_date_filter!='custom':
            self.start_date=False
            self.end_date=False
        if self.sh_date_filter == 'this_month':
            self.start_date = date(today.year, today.month, 1)
            self.end_date = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])

        if self.sh_date_filter == 'this_year':
            self.start_date = date(today.year, 1, 1)
            self.end_date = date(today.year, 12, 31)

        if self.sh_date_filter == 'last_month':
            prev_month = today - relativedelta(months=1)
            self.start_date = date(prev_month.year, prev_month.month, 1)
            self.end_date = date(prev_month.year, prev_month.month, calendar.monthrange(prev_month.year, prev_month.month)[1])

        if self.sh_date_filter == 'last_year':
            self.start_date = date((today.year-1), 1, 1)
            self.end_date = date((today.year-1), 12, 31)

        if self.sh_date_filter == 'this_quarter':
            q_start_month = 3 * currQuarter - 2
            self.start_date = date(today.year, q_start_month, 1)
            self.end_date = (datetime(today.year, q_start_month, 1) + relativedelta(months=3, days=-1)).date()

        if self.sh_date_filter == 'last_quarter':

            current_quar_start = datetime(today.year, 3 * currQuarter - 2, 1)

            self.start_date = datetime(today.year, current_quar_start.month, 1) + relativedelta(months=-3)
            self.end_date = current_quar_start + timedelta(days=-1)


        if self.customer_rank > 0 and self.start_date and self.end_date:

            self.sh_filter_customer_statement_ids.sudo().unlink()
            statement_lines = []

            account_id = self.property_account_receivable_id.id
            company_ids=[]
            if self.env.context and self.env.context.get('allowed_company_ids'):
                company_ids= self.env.context.get('allowed_company_ids')

            partner_list=[self]
            partner_ids=[self.id]
            considered_payment_ids = set()
            account_ids=[self.property_account_receivable_id.id]
            if self.company_type == 'company':
                if self.child_ids:
                    partner_list.extend(self.child_ids)
                    partner_ids.extend(self.child_ids.ids)
                    account_ids.extend(self.child_ids.mapped('property_account_receivable_id').ids)

            move_lines = self.env["account.move.line"].search(
                [
                    ("partner_id", "in", partner_ids),
                    ("date", "<", self.start_date),
                    ("account_id", "in", account_ids),
                    ("parent_state", "=", "posted"),
                    ("company_id","in",company_ids)
                ]
            )

            balance = sum(move_lines.mapped("debit")) - sum(move_lines.mapped("credit"))

            statement_lines.append(
                (0,0,{
                        "name": "Opening Balance",
                        "currency_id": move_lines[0].currency_id.id
                        if move_lines
                        else self.currency_id.id,
                        "sh_filter_balance": balance,
                        "sh_filter_type" : 'a'
                    },
                )
            )
            if self.payment_state:
                moves = (
                    self.env["account.move"].sudo().search([
                            ("partner_id", "in", partner_ids),
                            ("move_type", "in", ["out_invoice", "out_refund"]),
                            ("invoice_date", ">=", self.start_date),
                            ("invoice_date", "<=", self.end_date),
                            ("state", "not in", ["draft", "cancel"]),
                            ('payment_state','=',self.payment_state),
                            ("company_id","in",company_ids)
                        ]
                    )
                )
            else:
                moves = (
                    self.env["account.move"].sudo().search([
                            ("partner_id", "in", partner_ids),
                            ("move_type", "in", ["out_invoice", "out_refund"]),
                            ("invoice_date", ">=", self.start_date),
                            ("invoice_date", "<=", self.end_date),
                            ("state", "not in", ["draft", "cancel"]),
                            ("company_id","in",company_ids)
                        ]
                    )
                )
            if moves:

                for move in moves:

                    statement_vals = {
                        "sh_account": self.property_account_receivable_id.name,
                        "name": move.name,
                        "currency_id": move.currency_id.id,
                        "sh_filter_invoice_date": move.invoice_date,
                        "sh_filter_due_date": move.invoice_date_due,

                    }
                    if move.move_type == "out_invoice":
                        payments = move._get_reconciled_payments()
                        if not payments and move.amount_total - move.amount_residual:
                             payments = move._get_reconciled_amls().move_id
                        
                        if payments:
                            for pay in payments.filtered(lambda p: p._name == 'account.payment'):
                                applied_sum = sum(
                                    (m.amount_total - m.amount_residual) * 
                                    (pay.amount / sum(m.matched_payment_ids.mapped('amount')))
                                    for m in pay.matched_move_ids
                                )
                                if pay.currency_id.is_zero(pay.amount - applied_sum):
                                     considered_payment_ids.add(pay.id)

                        last_payment = payments.sorted(lambda p: p.date)[-1] if payments else False

                        payment_ref = last_payment.name if last_payment else False
                        payment_date = last_payment.date if last_payment else False
                        statement_vals.update(
                            {
                                "sh_filter_amount": move.amount_total,
                                "sh_filter_paid_amount": move.amount_total
                                - move.amount_residual,
                                "sh_filter_balance": move.amount_total
                                - (move.amount_total - move.amount_residual),
                                 'sh_filter_total_balance':0.0,
                                 "sh_filter_payment_date":payment_date,
                                "sh_filter_payment_ref_no":payment_ref,

                            }
                        )

                    elif move.move_type == "out_refund":
                        statement_vals.update({
                                "sh_filter_amount": move.amount_total*-1,
                                "sh_filter_paid_amount": (move.amount_total- move.amount_residual)*-1,
                                "sh_filter_balance": move.amount_residual*-1,
                                'sh_filter_total_balance':0.0

                            }
                        )
                    statement_lines.append((0, 0, statement_vals))

            advanced_payments_inbound = (
                self.env["account.payment"].sudo().search([
                        ("partner_id", "in", partner_ids),
                        ("date", ">=", self.start_date),
                        ("date", "<=", self.end_date),
                        ("state", "in", ["paid"]),
                        ("payment_type", "in", ["inbound"]),
                        ("partner_type", "in", ["customer"]),
                        ("id", "not in", list(considered_payment_ids) or [0]),
                        ("company_id","in",company_ids)
                    ]
                )
            )
            if advanced_payments_inbound:
                for advance_payment in advanced_payments_inbound:
                    total_paid_amount = 0.0

                    domain = [
                        ('account_id.account_type', 'in',('asset_receivable', 'liability_payable')),
                        ('parent_state', '=', 'posted'),
                        ('payment_id', '=', advance_payment.id),
                        ("company_id","in",company_ids)
                    ]
                    unpaid_move=self.env['account.move.line'].search(domain)
                    if unpaid_move:
                        unpaid_amount=sum(unpaid_move.mapped('amount_residual_currency'))
                        advance_payment_amount = advance_payment.amount
                        total_paid_amount = advance_payment.amount-abs(unpaid_amount)

                        if total_paid_amount < advance_payment_amount:
                            statement_vals = {
                                "sh_account": advance_payment.destination_account_id.name,
                                "name": advance_payment.name,
                                "currency_id": advance_payment.currency_id.id,
                                "sh_filter_invoice_date": False,
                                "sh_filter_due_date": False,
                                "sh_filter_amount": 0.0,
                                "sh_filter_paid_amount": abs(unpaid_amount),
                                "sh_filter_balance": -abs(unpaid_amount),
                                "sh_filter_payment_date":advance_payment.date,
                                "sh_filter_payment_ref_no":advance_payment.name

                            }
                            statement_lines.append((0, 0, statement_vals))
                    else:
                        statement_vals = {
                            "sh_account": advance_payment.destination_account_id.name,
                            "name": advance_payment.name,
                            "currency_id": advance_payment.currency_id.id,
                            "sh_filter_invoice_date": False,
                            "sh_filter_due_date": False,
                            "sh_filter_amount": 0.0,
                            "sh_filter_paid_amount": advance_payment.amount,
                            "sh_filter_balance": -(advance_payment.amount),
                            "sh_filter_payment_date":advance_payment.date,
                            "sh_filter_payment_ref_no":advance_payment.name

                        }
                        statement_lines.append((0, 0, statement_vals))

            advanced_payments_outbound = (
                self.env["account.payment"].sudo().search(
                    [
                        ("partner_id", "in", partner_ids),
                        ("date", ">=", self.start_date),
                        ("date", "<=", self.end_date),
                        ("state", "in", ["paid"]),
                        ("payment_type", "in", ["outbound"]),
                        ("partner_type", "in", ["customer"]),
                        ("id", "not in", list(considered_payment_ids) or [0]),
                        ("company_id","in",company_ids)
                    ]
                )
            )
            if advanced_payments_outbound:
                for advance_payment in advanced_payments_outbound:
                    total_paid_amount = 0.0
                    domain = [
                        ('account_id.account_type', 'in',('asset_receivable', 'liability_payable')),
                        ('parent_state', '=', 'posted'),
                        ('payment_id', '=', advance_payment.id),
                        ("company_id","in",company_ids)
                    ]
                    unpaid_move=self.env['account.move.line'].search(domain)
                    if unpaid_move:
                        unpaid_amount=sum(unpaid_move.mapped('amount_residual_currency'))
                        advance_payment_amount = advance_payment.amount


                        total_paid_amount=advance_payment_amount-unpaid_amount
                        if total_paid_amount < advance_payment_amount:
                            statement_vals = {
                                "sh_account": advance_payment.destination_account_id.name,
                                "name": advance_payment.name,
                                "currency_id": advance_payment.currency_id.id,
                                "sh_filter_invoice_date": False,
                                "sh_filter_due_date": False,
                                "sh_filter_amount": 0,
                                "sh_filter_paid_amount": abs(unpaid_amount),
                                "sh_filter_balance": abs(unpaid_amount),
                                "sh_filter_payment_date":advance_payment.date,
                                "sh_filter_payment_ref_no":advance_payment.name,
                                "sh_filter_payment_date":advance_payment.date,
                                "sh_filter_payment_ref_no":advance_payment.name


                            }
                            statement_lines.append((0, 0, statement_vals))
                    else:
                        # The "Amount Paid" on the statement should be the total amount of the payment.
                        # The "Balance" impact should also be the total amount of the payment.
                        statement_vals = {
                            "sh_account": advance_payment.destination_account_id.name,
                            "name": advance_payment.name,
                            "currency_id": advance_payment.currency_id.id,
                            "sh_filter_invoice_date": False,
                            "sh_filter_due_date": False,
                            "sh_filter_amount": 0,
                            "sh_filter_paid_amount": abs(advance_payment.amount),
                            "sh_filter_balance": abs(advance_payment.amount),
                            "sh_filter_payment_date":advance_payment.date,
                            "sh_filter_payment_ref_no":advance_payment.name

                        }
                        statement_lines.append((0, 0, statement_vals))

            self.sh_filter_customer_statement_ids = statement_lines

            # ------------------------------
            # Calculate running total balance
        #    # Sort lines by invoice/payment date
            all_lines = self.sh_filter_customer_statement_ids.sorted(
                key=lambda l: l.sh_filter_invoice_date or date.today()
            )

            running_total = 0.0

            for line in all_lines:
                # Base balance
                line_balance = line.sh_filter_balance

                # Payment entries decrease the balance
                if line.sh_filter_paid_amount and not line.name.startswith("INV"):
                    line_balance = -line.sh_filter_paid_amount

                # Add to cumulative total
                running_total += line_balance

                # Store final running total
                line.sh_filter_total_balance = running_total








    def action_print_filter_customer_statement(self):
        return self.env.ref(
            "sh_customer_statement.action_report_sh_customer_filtered_statement"
        ).report_action(self)

    def action_send_filter_customer_statement(self):
        self.ensure_one()
        template = self.env.ref(
            "sh_customer_statement.sh_customer_filter_statement_mail_template"
        )
        if template:
            mail = template.sudo().send_mail(self.id, force_send=True)
            mail_id = self.env["mail.mail"].sudo().browse(mail)
            if mail_id:
                self.env["sh.customer.mail.history"].sudo().create(
                    {
                        "name": "Customer Account Statement by Date",
                        "sh_statement_type": "customer_statement_filter",
                        "sh_current_date": fields.Datetime.now(),
                        "sh_partner_id": self.id,
                        "sh_mail_id": mail_id.id,
                        "sh_mail_status": mail_id.state,
                    }
                )

    def action_view_customer_history(self):
        self.ensure_one()
        return {
            "name": "Mail Log History",
            "type": "ir.actions.act_window",
            "res_model": "sh.customer.mail.history",
            "view_mode": "list,form",
            "domain": [("sh_partner_id", "=", self.id)],
            "target": "current",
        }

    def action_print_filter_customer_statement_xls(self):
        workbook = xlwt.Workbook()
        heading_format = xlwt.easyxf(
            "font:height 300,bold True;pattern: pattern solid, fore_colour gray25;align: horiz center;align: vert center;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        normal = xlwt.easyxf("font:bold True;align: horiz center;align: vert center")
        cyan_text = xlwt.easyxf(
            "font:bold True,color aqua;align: horiz center;align: vert center"
        )
        green_text = xlwt.easyxf(
            "font:bold True,color green;align: horiz center;align: vert center"
        )
        red_text = xlwt.easyxf(
            "font:bold True,color red;align: horiz center;align: vert center"
        )
        bold_center = xlwt.easyxf(
            "font:height 225,bold True;pattern: pattern solid,fore_colour gray25;align: horiz center;align: vert center;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        date_style = xlwt.easyxf(
            "font:height 225,bold True;pattern: pattern solid,fore_colour gray25;align: vert center;align: horiz right;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        totals = xlwt.easyxf(
            "font:height 225,bold True;pattern: pattern solid,fore_colour gray25;align: horiz center;align: vert center;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        worksheet = workbook.add_sheet(
            "Customer Statement Filter By Date", cell_overwrite_ok=True
        )

        header_dark = xlwt.easyxf(
            "font:height 225,bold True"
        )

        worksheet.row(0).height = 1200
        worksheet.row(1).height = 1200
        worksheet.row(3).height = 380
        worksheet.row(4).height = 320
        worksheet.row(10).height = 400
        worksheet.col(0).width = 5500
        worksheet.col(1).width = 6000
        worksheet.col(2).width = 4800
        worksheet.col(3).width = 4800
        worksheet.col(4).width = 5500
        worksheet.col(5).width = 5500
        worksheet.col(6).width = 5500
        worksheet.col(7).width = 8000
        worksheet.col(8).width = 5500
        worksheet.col(9).width = 8000


        address = ""
        if self.street:
            address += self.street
        if self.street2:
            address += " "+self.street2
        if self.city:
            address += "\n"+self.city
        if self.state_id:
            address += " "+self.state_id.name
        if self.zip:
            address += " "+self.zip
        if self.country_id:
            address += "\n"+self.country_id.name
            if self.vat:
                address += " - "+self.vat

        company_id=self.env.company
        company_address = company_id.name
        if company_id.street:
            company_address += "\n"+company_id.street
        if company_id.street2:
            company_address += " "+company_id.street2
        if company_id.city:
            company_address += "\n"+company_id.city
        if company_id.state_id:
            company_address += " "+company_id.state_id.name
        if company_id.zip:
            company_address += " "+company_id.zip
        if company_id.country_id:
            company_address += "\n"+company_id.country_id.name
            if company_id.vat:
                company_address += " - "+company_id.vat

        if company_address:
            worksheet.write_merge(0, 0, 0, 2, company_address,header_dark)
        if address:
            worksheet.write_merge(1, 1, 0, 2, address,header_dark)

        worksheet.write(3, 0, "Date From", date_style)
        if self.start_date:
            worksheet.write(3, 1, str(self.start_date), normal)
        worksheet.write(3, 2, "Date To", date_style)
        if self.end_date:
            worksheet.write(3, 3, str(self.end_date), normal)
        worksheet.write_merge(6, 7, 0, 9, self.name, heading_format)
        worksheet.write(10, 0, "Number", bold_center)
        worksheet.write(10, 1, "Account", bold_center)
        worksheet.write(10, 2, "Date", bold_center)
        worksheet.write(10, 3, "Due Date", bold_center)
        worksheet.write(10, 4, "Payment Date", bold_center)
        worksheet.write(10, 5, "Total Amount", bold_center)
        worksheet.write(10, 6, "Paid Amount", bold_center)
        worksheet.write(10, 7, "Payment Ref No.", bold_center)
        worksheet.write(10, 8, "Balance", bold_center)
        worksheet.write(10, 9, "Total Balance", bold_center)


        total_amount = 0
        total_paid_amount = 0
        total_balance = 0
        k = 11

        if self.sh_filter_customer_statement_ids:
            sorted_lines = self.sh_filter_customer_statement_ids.sorted(lambda l: (l.sh_filter_invoice_date or l.sh_filter_payment_date or date.today()))
            for j in sorted_lines:
                worksheet.row(k).height = 350
                style = normal
                if j.sh_filter_amount == j.sh_filter_balance:
                    if j.name == "Opening Balance":
                        style = green_text
                    else:
                        style = cyan_text
                elif j.sh_filter_balance == 0:
                    style = green_text
                else:
                    style = red_text

                worksheet.write(k, 0, j.name, style)
                worksheet.write(k, 1, j.sh_account or "", style)
                worksheet.write(k, 2, str(j.sh_filter_invoice_date) if j.sh_filter_invoice_date else "", style)
                worksheet.write(k, 3, str(j.sh_filter_due_date) if j.sh_filter_due_date else "", style)
                worksheet.write(k, 4, str(j.sh_filter_payment_date) if j.sh_filter_payment_date else "", style)
                worksheet.write(k, 5, str(j.currency_id.symbol) + str("{:.2f}".format(j.sh_filter_amount)), style)
                worksheet.write(k, 6, str(j.currency_id.symbol) + str("{:.2f}".format(j.sh_filter_paid_amount)), style)
                worksheet.write(k, 7, j.sh_filter_payment_ref_no or "", style)
                worksheet.write(k, 8, str(j.currency_id.symbol) + str("{:.2f}".format(j.sh_filter_balance)), style)
                worksheet.write(k, 9, str(j.currency_id.symbol) + str("{:.2f}".format(j.sh_filter_total_balance)), style)

                k = k + 1
                if j.name != "Opening Balance":
                    total_amount += j.sh_filter_amount
                    total_paid_amount += j.sh_filter_paid_amount
                total_balance += j.sh_filter_balance

        if self.sh_filter_customer_statement_ids:
            worksheet.write(k, 5, str("{:.2f}".format(total_amount)), totals)
            worksheet.row(k).height = 350
            worksheet.write(k, 6, str("{:.2f}".format(total_paid_amount)), totals)
            worksheet.write(k, 8, str("{:.2f}".format(total_balance)), totals)

        fp = io.BytesIO()
        workbook.save(fp)
        data = base64.encodebytes(fp.getvalue())
        IrAttachment = self.env["ir.attachment"]
        attachment_vals = {
            "name": "Customer Statement Filter By Date.xls",
            "res_model": "ir.ui.view",
            "type": "binary",
            "datas": data,
            "public": True,
        }
        fp.close()

        attachment = IrAttachment.search(
            [
                ("name", "=", "Customer Statement Filter By Date"),
                ("type", "=", "binary"),
                ("res_model", "=", "ir.ui.view"),
            ],
            limit=1,
        )
        if attachment:
            attachment.write(attachment_vals)
        else:
            attachment = IrAttachment.create(attachment_vals)

        if not attachment:
            raise UserError("There is no attachments...")

        url = "/web/content/" + str(attachment.id) + "?download=true"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "current",
        }

    def action_print_customer_statement_xls(self):
        workbook = xlwt.Workbook()
        heading_format = xlwt.easyxf(
            "font:height 300,bold True;pattern: pattern solid, fore_colour gray25;align: horiz center;align: vert center;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        normal = xlwt.easyxf("font:bold True;align: horiz center;align: vert center")
        cyan_text = xlwt.easyxf(
            "font:bold True,color aqua;align: horiz center;align: vert center"
        )
        green_text = xlwt.easyxf(
            "font:bold True,color green;align: horiz center;align: vert center"
        )
        red_text = xlwt.easyxf(
            "font:bold True,color red;align: horiz center;align: vert center"
        )
        bold_center = xlwt.easyxf(
            "font:height 225,bold True;pattern: pattern solid,fore_colour gray25;align: horiz center;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        date_style = xlwt.easyxf(
            "font:height 225,bold True;pattern: pattern solid,fore_colour gray25;align: vert center;align: horiz right;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        totals = xlwt.easyxf(
            "font:height 225,bold True;pattern: pattern solid,fore_colour gray25;align: horiz center;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        worksheet = workbook.add_sheet("Customer Statement", cell_overwrite_ok=True)

        header_dark = xlwt.easyxf(
            "font:height 225,bold True"
        )

        address = ""
        if self.street:
            address += self.street
        if self.street2:
            address += " "+self.street2
        if self.city:
            address += "\n"+self.city
        if self.state_id:
            address += " "+self.state_id.name
        if self.zip:
            address += " "+self.zip
        if self.country_id:
            address += "\n"+self.country_id.name
            if self.vat:
                address += " - "+self.vat

        company_id=self.env.company
        company_address = company_id.name
        if company_id.street:
            company_address += "\n"+company_id.street
        if company_id.street2:
            company_address += " "+company_id.street2
        if company_id.city:
            company_address += "\n"+company_id.city
        if company_id.state_id:
            company_address += " "+company_id.state_id.name
        if company_id.zip:
            company_address += " "+company_id.zip
        if company_id.country_id:
            company_address += "\n"+company_id.country_id.name
            if company_id.vat:
                company_address += " - "+company_id.vat

        if company_address:
            worksheet.write_merge(0, 0, 0, 2, company_address,header_dark)
        if address:
            worksheet.write_merge(1, 1, 0, 2, address,header_dark)

        if not self.env.context.get('sh_hide_dates', True):
            worksheet.write(3, 0, "Date From", date_style)
            if self.start_date:
                worksheet.write(3, 1, str(self.start_date), normal)
            worksheet.write(3, 2, "Date To", date_style)
            if self.end_date:
                worksheet.write(3, 3, str(self.end_date), normal)

        worksheet.row(0).height = 1200
        worksheet.row(1).height = 1200
        worksheet.row(7).height = 400

        worksheet.col(2).width = 4800
        worksheet.col(3).width = 4800
        worksheet.col(4).width = 5500
        worksheet.col(5).width = 5500
        worksheet.col(6).width = 5500
        worksheet.col(0).width = 8000
        worksheet.col(1).width = 6000
        worksheet.col(7).width = 8000
        worksheet.col(9).width = 8000
        worksheet.write_merge(4, 5, 0, 6, self.name, heading_format)
        worksheet.write(7, 0, "Number", bold_center)
        worksheet.write(7, 1, "Account", bold_center)
        worksheet.write(7, 2, "Date", bold_center)
        worksheet.write(7, 3, "Due Date", bold_center)
        worksheet.write(7, 4, "Payment Date", bold_center)
        worksheet.write(7, 5, "Total Amount", bold_center)
        worksheet.write(7, 6, "Paid Amount", bold_center)
        worksheet.write(7, 7, "Payment Ref No.", bold_center)
        worksheet.write(7, 8, "Balance", bold_center)
        worksheet.write(7, 9, "Total Balance", bold_center)

        total_amount = 0
        total_paid_amount = 0
        total_balance = 0
        k = 8

        statement_ids = self.sh_customer_statement_ids
        if not self.env.context.get('sh_hide_dates', True):
            if self.start_date:
                statement_ids = statement_ids.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) >= self.start_date)
            if self.end_date:
                statement_ids = statement_ids.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) <= self.end_date)

        today = fields.Date.today()
        b0_30 = 0.0
        b31_60 = 0.0
        b61_90 = 0.0
        b91p = 0.0

        adv0_30 = 0.0
        adv31_60 = 0.0
        adv61_90 = 0.0
        adv91p = 0.0

        if statement_ids:
            standard_lines = statement_ids.filtered(lambda l: l.sh_customer_amount != 0.0)
            b0_30 = sum(standard_lines.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) > today - timedelta(days=30)).mapped('sh_customer_balance'))
            b31_60 = sum(standard_lines.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) <= today - timedelta(days=30) and (l.sh_customer_invoice_date or l.sh_payment_date) > today - timedelta(days=60)).mapped('sh_customer_balance'))
            b61_90 = sum(standard_lines.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) <= today - timedelta(days=60) and (l.sh_customer_invoice_date or l.sh_payment_date) > today - timedelta(days=90)).mapped('sh_customer_balance'))
            b91p = sum(standard_lines.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) <= today - timedelta(days=90)).mapped('sh_customer_balance'))

            adv_lines = statement_ids.filtered(lambda l: l.sh_customer_amount == 0.0 or (l.sh_customer_amount != 0.0 and l.sh_customer_balance < 0.0))
            adv0_30 = sum(adv_lines.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) > today - timedelta(days=30)).mapped(lambda l: abs(l.sh_customer_balance)))
            adv31_60 = sum(adv_lines.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) <= today - timedelta(days=30) and (l.sh_customer_invoice_date or l.sh_payment_date) > today - timedelta(days=60)).mapped(lambda l: abs(l.sh_customer_balance)))
            adv61_90 = sum(adv_lines.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) <= today - timedelta(days=60) and (l.sh_customer_invoice_date or l.sh_payment_date) > today - timedelta(days=90)).mapped(lambda l: abs(l.sh_customer_balance)))
            adv91p = sum(adv_lines.filtered(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date) and (l.sh_customer_invoice_date or l.sh_payment_date) <= today - timedelta(days=90)).mapped(lambda l: abs(l.sh_customer_balance)))

            for j in statement_ids.sorted(lambda l: (l.sh_customer_invoice_date or l.sh_payment_date)):
                worksheet.row(k).height = 350
                style = normal
                if j.sh_customer_amount == j.sh_customer_balance:
                    style = cyan_text
                elif j.sh_customer_balance == 0:
                    style = green_text
                else:
                    style = red_text

                worksheet.write(k, 0, j.name, style)
                worksheet.write(k, 1, j.sh_account, style)
                worksheet.write(k, 2, str(j.sh_customer_invoice_date) if j.sh_customer_invoice_date else '', style)
                worksheet.write(k, 3, str(j.sh_customer_due_date) if j.sh_customer_due_date else '', style)
                worksheet.write(k, 4, str(j.sh_payment_date) if j.sh_payment_date else '', style)
                worksheet.write(k, 5, str(j.currency_id.symbol) + str("{:.2f}".format(j.sh_customer_amount)), style)
                worksheet.write(k, 6, str(j.currency_id.symbol) + str("{:.2f}".format(j.sh_customer_paid_amount)), style)
                worksheet.write(k, 7, j.sh_payment_reference or '', style)
                worksheet.write(k, 8, str(j.currency_id.symbol) + str("{:.2f}".format(j.sh_customer_balance)), style)
                worksheet.write(k, 9, str(j.currency_id.symbol) + str("{:.2f}".format(j.sh_total_balance)), style)

                k = k + 1
                total_amount += j.sh_customer_amount
                total_paid_amount += j.sh_customer_paid_amount
                total_balance += j.sh_customer_balance

        if statement_ids:
            worksheet.write(k, 5, str("{:.2f}".format(total_amount)), totals)
            worksheet.row(k).height = 350
            worksheet.write(k, 6, str("{:.2f}".format(total_paid_amount)), totals)
            worksheet.write(k, 8, str("{:.2f}".format(total_balance)), totals)
        if self.env.context.get('is_show_aging_bucket') or self.env.context.get('always_show_bucket'):
            worksheet.row(k + 3).height = 400
            worksheet.row(k + 4).height = 400
            worksheet.row(k + 5).height = 400
            worksheet.write(k + 3, 0, "Gap Between Days", bold_center)
            worksheet.write(k + 3, 1, "0-30(Days)", bold_center)
            worksheet.write(k + 3, 2, "31-60(Days)", bold_center)
            worksheet.write(k + 3, 3, "61-90(Days)", bold_center)
            worksheet.write(k + 3, 4, "91+(Days)", bold_center)
            worksheet.write(k + 3, 5, "Total", bold_center)
            worksheet.write(k + 4, 0, "Balance Amount", bold_center)
            worksheet.write(k + 5, 0, "Unallocated Balance Amount", bold_center)
            if statement_ids:
                worksheet.write(
                    k + 4, 1, str("{:.2f}".format(b0_30)), normal
                )
                worksheet.write(
                    k + 4, 2, str("{:.2f}".format(b31_60)), normal
                )
                worksheet.write(
                    k + 4, 3, str("{:.2f}".format(b61_90)), normal
                )
                worksheet.write(
                    k + 4, 4, str("{:.2f}".format(b91p)), normal
                )
                worksheet.write(
                    k + 4, 5, str("{:.2f}".format(b0_30 + b31_60 + b61_90 + b91p)), normal
                )

                worksheet.write(
                    k + 5, 1, str("{:.2f}".format(adv0_30)), normal
                )
                worksheet.write(
                    k + 5, 2, str("{:.2f}".format(adv31_60)), normal
                )
                worksheet.write(
                    k + 5, 3, str("{:.2f}".format(adv61_90)), normal
                )
                worksheet.write(
                    k + 5, 4, str("{:.2f}".format(adv91p)), normal
                )
                worksheet.write(
                    k + 5, 5, str("{:.2f}".format(adv0_30 + adv31_60 + adv61_90 + adv91p)), normal
                )

        fp = io.BytesIO()
        workbook.save(fp)
        data = base64.encodebytes(fp.getvalue())
        IrAttachment = self.env["ir.attachment"]
        attachment_vals = {
            "name": "Customer Statement.xls",
            "res_model": "ir.ui.view",
            "type": "binary",
            "datas": data,
            "public": True,
        }
        fp.close()

        attachment = IrAttachment.search(
            [
                ("name", "=", "Customer Statement"),
                ("type", "=", "binary"),
                ("res_model", "=", "ir.ui.view"),
            ],
            limit=1,
        )
        if attachment:
            attachment.write(attachment_vals)
        else:
            attachment = IrAttachment.create(attachment_vals)

        if not attachment:
            raise UserError("There is no attachments...")

        url = "/web/content/" + str(attachment.id) + "?download=true"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "current",
        }

    def action_print_customer_due_statement_xls(self):
        workbook = xlwt.Workbook()
        heading_format = xlwt.easyxf(
            "font:height 300,bold True;pattern: pattern solid, fore_colour gray25;align: horiz center;align: vert center;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        red_text = xlwt.easyxf(
            "font:bold True,color red;align: horiz center;align: vert center"
        )
        center_text = xlwt.easyxf("align: horiz center;align: vert center")
        bold_center = xlwt.easyxf(
            "font:height 225,bold True;pattern: pattern solid,fore_colour gray25;align: horiz center;align: vert center;borders: left thin, right thin, bottom thin,top thin,top_color gray40,bottom_color gray40,left_color gray40,right_color gray40"
        )
        date_style = xlwt.easyxf(
            "font:height 225,bold True;pattern: pattern solid,fore_colour gray25;borders: left thin, right thin, bottom thin;align: vert center;align: horiz left"
        )
        normal = xlwt.easyxf("font:bold True;align: horiz center;align: vert center")
        worksheet = workbook.add_sheet(
            "Customer Overdue Statement", cell_overwrite_ok=True
        )

        header_dark = xlwt.easyxf(
            "font:height 225,bold True"
        )

        address = ""
        if self.street:
            address += self.street
        if self.street2:
            address += " "+self.street2
        if self.city:
            address += "\n"+self.city
        if self.state_id:
            address += " "+self.state_id.name
        if self.zip:
            address += " "+self.zip
        if self.country_id:
            address += "\n"+self.country_id.name
            if self.vat:
                address += " - "+self.vat

        company_id=self.env.company
        company_address = company_id.name
        if company_id.street:
            company_address += "\n"+company_id.street
        if company_id.street2:
            company_address += " "+company_id.street2
        if company_id.city:
            company_address += "\n"+company_id.city
        if company_id.state_id:
            company_address += " "+company_id.state_id.name
        if company_id.zip:
            company_address += " "+company_id.zip
        if company_id.country_id:
            company_address += "\n"+company_id.country_id.name
            if company_id.vat:
                company_address += " - "+company_id.vat

        if company_address:
            worksheet.write_merge(0, 0, 0, 2, company_address,header_dark)
        if address:
            worksheet.write_merge(1, 1, 0, 2, address,header_dark)

        if not self.env.context.get('sh_hide_dates', True):
            worksheet.write(3, 1, "Date From", date_style)
            if self.start_date:
                worksheet.write(3, 2, str(self.start_date), normal)
            worksheet.write(3, 3, "Date To", date_style)
            if self.end_date:
                worksheet.write(3, 4, str(self.end_date), normal)

        tz = self.env.context.get("tz") or self.env.user.tz or "UTC"
        timezone = pytz.timezone(tz)

        now = datetime.now(timezone)
        today_date = now.strftime("%d/%m/%Y %H:%M:%S")

        worksheet.write(3, 0, str(str("Date") + str(": ") + str(today_date)), date_style)
        worksheet.row(0).height = 1200
        worksheet.row(1).height = 1200
        worksheet.row(3).height = 350
        worksheet.row(8).height = 350
        worksheet.col(0).width = 8000
        worksheet.col(1).width = 6000
        worksheet.col(2).width = 4800
        worksheet.col(3).width = 4800
        worksheet.col(4).width = 5500
        worksheet.col(5).width = 5500
        worksheet.col(6).width = 5500
        worksheet.row(13).height = 350

        worksheet.write_merge(5, 6, 0, 6, self.name, heading_format)
        worksheet.write(8, 0, "Number", bold_center)
        worksheet.write(8, 1, "Account", bold_center)
        worksheet.write(8, 2, "Date", bold_center)
        worksheet.write(8, 3, "Due Date", bold_center)
        worksheet.write(8, 4, "Total Amount", bold_center)
        worksheet.write(8, 5, "Paid Amount", bold_center)
        worksheet.write(8, 6, "Balance", bold_center)

        total_amount = 0
        total_paid_amount = 0
        total_balance = 0
        k = 9

        due_statement_ids = self.sh_customer_due_statement_ids
        if not self.env.context.get('sh_hide_dates', True):
            if self.start_date:
                due_statement_ids = due_statement_ids.filtered(lambda l: l.sh_due_customer_due_date and l.sh_due_customer_due_date >= self.start_date)
            if self.end_date:
                due_statement_ids = due_statement_ids.filtered(lambda l: l.sh_due_customer_due_date and l.sh_due_customer_due_date <= self.end_date)

        if due_statement_ids:
            for i in due_statement_ids.sorted(lambda l: l.sh_due_customer_due_date):
                worksheet.row(k).height = 350
                if (
                    i.sh_due_customer_due_date
                    and i.sh_today
                    and i.sh_due_customer_due_date < i.sh_today
                ):
                    worksheet.write(k, 0, i.name, red_text)
                    worksheet.write(k, 1, i.sh_account, red_text)
                    worksheet.write(
                        k, 2, str(i.sh_due_customer_invoice_date), red_text
                    )
                    if i.sh_due_customer_due_date:
                        worksheet.write(
                            k, 3, str(i.sh_due_customer_due_date), red_text
                        )
                    else:
                        worksheet.write(k, 3, "", red_text)
                    worksheet.write(
                        k,
                        4,
                        str(i.currency_id.symbol)
                        + str("{:.2f}".format(i.sh_due_customer_amount)),
                        red_text,
                    )
                    worksheet.write(
                        k,
                        5,
                        str(i.currency_id.symbol)
                        + str("{:.2f}".format(i.sh_due_customer_paid_amount)),
                        red_text,
                    )
                    worksheet.write(
                        k,
                        6,
                        str(i.currency_id.symbol)
                        + str("{:.2f}".format(i.sh_due_customer_balance)),
                        red_text,
                    )
                else:
                    worksheet.write(k, 0, i.name, center_text)
                    worksheet.write(k, 1, i.sh_account, center_text)
                    worksheet.write(
                        k, 2, str(i.sh_due_customer_invoice_date), center_text
                    )
                    if i.sh_due_customer_due_date:
                        worksheet.write(
                            k, 3, str(i.sh_due_customer_due_date), center_text
                        )
                    else:
                        worksheet.write(k, 3, "", center_text)
                    worksheet.write(
                        k,
                        4,
                        str(i.currency_id.symbol)
                        + str("{:.2f}".format(i.sh_due_customer_amount)),
                        center_text,
                    )
                    worksheet.write(
                        k,
                        5,
                        str(i.currency_id.symbol)
                        + str("{:.2f}".format(i.sh_due_customer_paid_amount)),
                        center_text,
                    )
                    worksheet.write(
                        k,
                        6,
                        str(i.currency_id.symbol)
                        + str("{:.2f}".format(i.sh_due_customer_balance)),
                        center_text,
                    )
                k = k + 1
                total_amount += i.sh_due_customer_amount
                total_paid_amount += i.sh_due_customer_paid_amount
                total_balance += i.sh_due_customer_balance

        if due_statement_ids:
            worksheet.write(k, 4, str("{:.2f}".format(total_amount)), bold_center)
            worksheet.row(k).height = 350
            worksheet.write(k, 5, str("{:.2f}".format(total_paid_amount)), bold_center)
            worksheet.write(k, 6, str("{:.2f}".format(total_balance)), bold_center)

        fp = io.BytesIO()
        workbook.save(fp)

        data = base64.encodebytes(fp.getvalue())
        IrAttachment = self.env["ir.attachment"]
        attachment_vals = {
            "name": "Customer Overdue Statement.xls",
            "res_model": "ir.ui.view",
            "type": "binary",
            "datas": data,
            "public": True,
        }
        fp.close()

        attachment = IrAttachment.search(
            [
                ("name", "=", "Customer Overdue Statement"),
                ("type", "=", "binary"),
                ("res_model", "=", "ir.ui.view"),
            ],
            limit=1,
        )
        if attachment:
            attachment.write(attachment_vals)
        else:
            attachment = IrAttachment.create(attachment_vals)

        if not attachment:
            raise UserError("There is no attachments...")

        url = "/web/content/" + str(attachment.id) + "?download=true"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "current",
        }

    @api.model
    def _run_auto_send_customer_statements(self):
        temp = []
        statement_partners_ids = (
            self.env["sh.customer.statement.config"].sudo().search([])
        )
        if statement_partners_ids:
            for statement in statement_partners_ids:
                for partner in statement.sh_partner_ids:
                    if partner.id not in temp:
                        temp.append(partner.id)
        partner_ids = self.env["res.partner"].sudo().search([("id", "not in", temp)])
        for partner in partner_ids:
            try:
                # for customer
                if partner.customer_rank > 0:
                    # for statement
                    if not partner.sh_dont_send_customer_statement_auto:
                        if (
                            self.env.company.sh_customer_statement_auto_send
                            and partner.sh_customer_statement_ids
                        ):

                            if self.env.company.filter_only_unpaid_and_send_that and not partner.sh_customer_statement_ids.filtered(lambda x:x.sh_filter_balance > 0):
                                return

                            if self.env.company.sh_customer_statement_action == "daily":
                                if self.env.company.sh_cus_daily_statement_template_id:
                                    mail = self.env.company.sh_cus_daily_statement_template_id.sudo().send_mail(
                                        partner.id, force_send=True
                                    )
                                    mail_id = self.env["mail.mail"].sudo().browse(mail)
                                    if (
                                        mail_id
                                        and self.env.company.sh_cust_create_log_history
                                    ):
                                        self.env[
                                            "sh.customer.mail.history"
                                        ].sudo().create(
                                            {
                                                "name": "Customer Account Statement",
                                                "sh_statement_type": "customer_statement",
                                                "sh_current_date": fields.Datetime.now(),
                                                "sh_partner_id": partner.id,
                                                "sh_mail_id": mail_id.id,
                                                "sh_mail_status": mail_id.state,
                                            }
                                        )
                            elif (
                                self.env.company.sh_customer_statement_action
                                == "weekly"
                            ):
                                today = fields.Date.today().weekday()
                                if int(self.env.company.sh_cust_week_day) == today:
                                    if (
                                        self.env.company.sh_cust_weekly_statement_template_id
                                    ):
                                        mail = self.env.company.sh_cust_weekly_statement_template_id.sudo().send_mail(
                                            partner.id, force_send=True
                                        )
                                        mail_id = (
                                            self.env["mail.mail"].sudo().browse(mail)
                                        )
                                        if (
                                            mail_id
                                            and self.env.company.sh_cust_create_log_history
                                        ):
                                            self.env[
                                                "sh.customer.mail.history"
                                            ].sudo().create(
                                                {
                                                    "name": "Customer Account Statement",
                                                    "sh_statement_type": "customer_statement",
                                                    "sh_current_date": fields.Datetime.now(),
                                                    "sh_partner_id": partner.id,
                                                    "sh_mail_id": mail_id.id,
                                                    "sh_mail_status": mail_id.state,
                                                }
                                            )
                            elif (
                                self.env.company.sh_customer_statement_action
                                == "monthly"
                            ):
                                monthly_day = self.env.company.sh_cust_monthly_date
                                today = fields.Date.today()
                                today_date = today.day
                                if self.env.company.sh_cust_monthly_end:
                                    last_day = calendar.monthrange(
                                        today.year, today.month
                                    )[1]
                                    if today_date == last_day:
                                        if self.env.company.sh_cust_monthly_template_id:
                                            mail = self.env.company.sh_cust_monthly_template_id.sudo().send_mail(
                                                partner.id, force_send=True
                                            )
                                            mail_id = (
                                                self.env["mail.mail"]
                                                .sudo()
                                                .browse(mail)
                                            )
                                            if (
                                                mail_id
                                                and self.env.company.sh_cust_create_log_history
                                            ):
                                                self.env[
                                                    "sh.customer.mail.history"
                                                ].sudo().create(
                                                    {
                                                        "name": "Customer Account Statement",
                                                        "sh_statement_type": "customer_statement",
                                                        "sh_current_date": fields.Datetime.now(),
                                                        "sh_partner_id": partner.id,
                                                        "sh_mail_id": mail_id.id,
                                                        "sh_mail_status": mail_id.state,
                                                    }
                                                )
                                else:
                                    if today_date == monthly_day:
                                        if self.env.company.sh_cust_monthly_template_id:
                                            mail = self.env.company.sh_cust_monthly_template_id.sudo().send_mail(
                                                partner.id, force_send=True
                                            )
                                            mail_id = (
                                                self.env["mail.mail"]
                                                .sudo()
                                                .browse(mail)
                                            )
                                            if (
                                                mail_id
                                                and self.env.company.sh_cust_create_log_history
                                            ):
                                                self.env[
                                                    "sh.customer.mail.history"
                                                ].sudo().create(
                                                    {
                                                        "name": "Customer Account Statement",
                                                        "sh_statement_type": "customer_statement",
                                                        "sh_current_date": fields.Datetime.now(),
                                                        "sh_partner_id": partner.id,
                                                        "sh_mail_id": mail_id.id,
                                                        "sh_mail_status": mail_id.state,
                                                    }
                                                )
                            elif (
                                self.env.company.sh_customer_statement_action
                                == "yearly"
                            ):
                                today = fields.Date.today()
                                today_date = today.day
                                today_month = today.strftime("%B").lower()
                                if (
                                    self.env.company.sh_cust_yearly_date == today_date
                                    and self.env.company.sh_cust_yearly_month
                                    == today_month
                                ):
                                    if self.env.company.sh_cust_yearly_template_id:
                                        mail = self.env.company.sh_cust_yearly_template_id.sudo().send_mail(
                                            partner.id, force_send=True
                                        )
                                        mail_id = (
                                            self.env["mail.mail"].sudo().browse(mail)
                                        )
                                        if (
                                            mail_id
                                            and self.env.company.sh_cust_create_log_history
                                        ):
                                            self.env[
                                                "sh.customer.mail.history"
                                            ].sudo().create(
                                                {
                                                    "name": "Customer Account Statement",
                                                    "sh_statement_type": "customer_statement",
                                                    "sh_current_date": fields.Datetime.now(),
                                                    "sh_partner_id": partner.id,
                                                    "sh_mail_id": mail_id.id,
                                                    "sh_mail_status": mail_id.state,
                                                }
                                            )
                    # for overdue statement
                    if not partner.sh_dont_send_due_customer_statement_auto:
                        if (
                            self.env.company.sh_customer_due_statement_auto_send
                            and partner.sh_customer_due_statement_ids
                        ):
                            if self.env.company.filter_only_unpaid_and_send_that and not partner.sh_customer_due_statement_ids.filtered(lambda x:x.sh_filter_balance > 0):
                                return

                            if (
                                self.env.company.sh_customer_due_statement_action
                                == "daily"
                            ):
                                if (
                                    self.env.company.sh_cus_due_daily_statement_template_id
                                ):
                                    mail = self.env.company.sh_cus_due_daily_statement_template_id.sudo().send_mail(
                                        partner.id, force_send=True
                                    )
                                    mail_id = self.env["mail.mail"].sudo().browse(mail)
                                    if (
                                        mail_id
                                        and self.env.company.sh_cust_due_create_log_history
                                    ):
                                        self.env[
                                            "sh.customer.mail.history"
                                        ].sudo().create(
                                            {
                                                "name": "Customer Account Overdue Statement",
                                                "sh_statement_type": "customer_overdue_statement",
                                                "sh_current_date": fields.Datetime.now(),
                                                "sh_partner_id": partner.id,
                                                "sh_mail_id": mail_id.id,
                                                "sh_mail_status": mail_id.state,
                                            }
                                        )
                            elif (
                                self.env.company.sh_customer_due_statement_action
                                == "weekly"
                            ):
                                today = fields.Date.today().weekday()
                                if int(self.env.company.sh_cust_due_week_day) == today:
                                    if (
                                        self.env.company.sh_cust_due_weekly_statement_template_id
                                    ):
                                        mail = self.env.company.sh_cust_due_weekly_statement_template_id.sudo().send_mail(
                                            partner.id, force_send=True
                                        )
                                        mail_id = (
                                            self.env["mail.mail"].sudo().browse(mail)
                                        )
                                        if (
                                            mail_id
                                            and self.env.company.sh_cust_due_create_log_history
                                        ):
                                            self.env[
                                                "sh.customer.mail.history"
                                            ].sudo().create(
                                                {
                                                    "name": "Customer Account Overdue Statement",
                                                    "sh_statement_type": "customer_overdue_statement",
                                                    "sh_current_date": fields.Datetime.now(),
                                                    "sh_partner_id": partner.id,
                                                    "sh_mail_id": mail_id.id,
                                                    "sh_mail_status": mail_id.state,
                                                }
                                            )
                            elif (
                                self.env.company.sh_customer_due_statement_action
                                == "monthly"
                            ):
                                monthly_day = self.env.company.sh_cust_due_monthly_date
                                today = fields.Date.today()
                                today_date = today.day
                                if self.env.company.sh_cust_due_monthly_end:
                                    last_day = calendar.monthrange(
                                        today.year, today.month
                                    )[1]
                                    if today_date == last_day:
                                        if (
                                            self.env.company.sh_cust_due_monthly_template_id
                                        ):
                                            mail = self.env.company.sh_cust_due_monthly_template_id.sudo().send_mail(
                                                partner.id, force_send=True
                                            )
                                            mail_id = (
                                                self.env["mail.mail"]
                                                .sudo()
                                                .browse(mail)
                                            )
                                            if (
                                                mail_id
                                                and self.env.company.sh_cust_due_create_log_history
                                            ):
                                                self.env[
                                                    "sh.customer.mail.history"
                                                ].sudo().create(
                                                    {
                                                        "name": "Customer Account Overdue Statement",
                                                        "sh_statement_type": "customer_overdue_statement",
                                                        "sh_current_date": fields.Datetime.now(),
                                                        "sh_partner_id": partner.id,
                                                        "sh_mail_id": mail_id.id,
                                                        "sh_mail_status": mail_id.state,
                                                    }
                                                )
                                else:
                                    if today_date == monthly_day:
                                        if (
                                            self.env.company.sh_cust_due_monthly_template_id
                                        ):
                                            mail = self.env.company.sh_cust_due_monthly_template_id.sudo().send_mail(
                                                partner.id, force_send=True
                                            )
                                            mail_id = (
                                                self.env["mail.mail"]
                                                .sudo()
                                                .browse(mail)
                                            )
                                            if (
                                                mail_id
                                                and self.env.company.sh_cust_due_create_log_history
                                            ):
                                                self.env[
                                                    "sh.customer.mail.history"
                                                ].sudo().create(
                                                    {
                                                        "name": "Customer Account Overdue Statement",
                                                        "sh_statement_type": "customer_overdue_statement",
                                                        "sh_current_date": fields.Datetime.now(),
                                                        "sh_partner_id": partner.id,
                                                        "sh_mail_id": mail_id.id,
                                                        "sh_mail_status": mail_id.state,
                                                    }
                                                )

                            elif (
                                self.env.company.sh_customer_due_statement_action
                                == "yearly"
                            ):
                                today = fields.Date.today()
                                today_date = today.day
                                today_month = today.strftime("%B").lower()
                                if (
                                    self.env.company.sh_cust_due_yearly_date
                                    == today_date
                                    and self.env.company.sh_cust_due_yearly_month
                                    == today_month
                                ):
                                    if self.env.company.sh_cust_due_yearly_template_id:
                                        mail = self.env.company.sh_cust_due_yearly_template_id.sudo().send_mail(
                                            partner.id, force_send=True
                                        )
                                        mail_id = (
                                            self.env["mail.mail"].sudo().browse(mail)
                                        )
                                        if (
                                            mail_id
                                            and self.env.company.sh_cust_due_create_log_history
                                        ):
                                            self.env[
                                                "sh.customer.mail.history"
                                            ].sudo().create(
                                                {
                                                    "name": "Customer Account Overdue Statement",
                                                    "sh_statement_type": "customer_overdue_statement",
                                                    "sh_current_date": fields.Datetime.now(),
                                                    "sh_partner_id": partner.id,
                                                    "sh_mail_id": mail_id.id,
                                                    "sh_mail_status": mail_id.state,
                                                }
                                            )
            except Exception as e:
                _logger.error("%s", e)
