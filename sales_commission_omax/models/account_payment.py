# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    salesperson_id = fields.Many2one(
        'res.partner',
        string='Salesperson',
        domain="[('is_salesperson', '=', True)]",
        compute='_compute_salesperson_id',
        store=True,
        readonly=False,
        index=True,
        help=(
            "Salesperson contact linked to this payment for reporting/grouping. "
            "It is inferred from reconciled invoices or the customer assigned salesperson."
        ),
    )

    @api.depends(
        'partner_id',
        'partner_id.assigned_salesperson_id',
        'invoice_ids.salesperson_id',
        'reconciled_invoice_ids.salesperson_id',
        'move_id.line_ids.matched_debit_ids',
        'move_id.line_ids.matched_credit_ids',
    )
    def _compute_salesperson_id(self):
        for payment in self:
            invoices = payment.reconciled_invoice_ids or payment.invoice_ids
            salespersons = invoices.mapped('salesperson_id').filtered(lambda p: p.is_salesperson).sorted(key=lambda p: p.id)

            if len(salespersons) == 1:
                payment.salesperson_id = salespersons
            elif len(salespersons) > 1:
                payment.salesperson_id = payment.partner_id.assigned_salesperson_id or salespersons[0]
            else:
                payment.salesperson_id = payment.partner_id.assigned_salesperson_id

