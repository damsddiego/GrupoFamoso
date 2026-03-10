# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    credit_check = fields.Boolean('Active Credit', help='Activate the credit limit feature')
    credit_warning = fields.Monetary('Warning Amount')
    credit_blocking = fields.Monetary('Blocking Amount')
    amount_due = fields.Monetary('Due Amount', compute='_compute_amount_due')
    has_overdue_invoices = fields.Boolean('Has Overdue Invoices', compute='_compute_has_overdue_invoices')
    overdue_amount = fields.Monetary('Overdue Amount', compute='_compute_overdue_amount', help='Total amount of overdue invoices')

    @api.depends('credit', 'debit')
    def _compute_amount_due(self):
        for rec in self:
            rec.amount_due = rec.credit - rec.debit
            partner_so = self.env['sale.order'].search([('partner_id', '=', rec.id), ('state', '=', 'sale')])
            for order in partner_so:
                if not order.invoice_ids:
                    rec.amount_due = rec.amount_due + order.amount_total
                else:
                    draft_invoice = order.invoice_ids.filtered(lambda x: x.state == 'draft')
                    rec.amount_due = rec.amount_due + sum(draft_invoice.mapped('amount_residual'))

    def _compute_has_overdue_invoices(self):
        """
        Check if partner has any overdue invoices (posted invoices past their due date)
        """
        for rec in self:
            rec.has_overdue_invoices = False
            if rec.id:
                today = fields.Date.today()
                overdue_invoices = self.env['account.move'].search([
                    ('partner_id', '=', rec.id),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('invoice_date_due', '<', today),
                ], limit=1)
                rec.has_overdue_invoices = bool(overdue_invoices)

    def _compute_overdue_amount(self):
        """
        Calculate total amount of overdue invoices
        """
        for rec in self:
            rec.overdue_amount = 0.0
            if rec.id:
                today = fields.Date.today()
                overdue_invoices = self.env['account.move'].search([
                    ('partner_id', '=', rec.id),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('invoice_date_due', '<', today),
                ])
                rec.overdue_amount = sum(overdue_invoices.mapped('amount_residual'))

    @api.constrains('credit_warning', 'credit_blocking')
    def _check_credit_amount(self):
        for credit in self:
            if credit.credit_warning > credit.credit_blocking:
                raise ValidationError(_('Warning amount should not be greater than blocking amount.'))
            if credit.credit_warning < 0 or credit.credit_blocking < 0:
                raise ValidationError(_('Warning amount or blocking amount should not be less than zero.'))


class ResCompany(models.Model):
    _inherit = 'res.company'

    accountant_email = fields.Char(string='Accountant email')