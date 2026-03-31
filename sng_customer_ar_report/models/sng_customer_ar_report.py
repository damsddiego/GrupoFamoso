# -*- coding: utf-8 -*-
"""
Customer Accounts Receivable Report — SQL VIEW model.

Design decisions:
- amount_invoiced uses SUM(am.amount_total_signed) — includes company-currency sign
  so it works correctly in multi-currency/multi-company setups.
- amount_due uses SUM(am.amount_residual_signed) — same reasoning.
- avg_days_to_pay is calculated ONLY from fully-paid invoices (amount_residual = 0).
  For each paid invoice, days_to_pay = MAX(apr.max_date) - am.invoice_date.
  MAX(apr.max_date) gives the date of the last reconciliation that cleared the invoice.
  If a client has no paid invoices, avg_days_to_pay = NULL (shown as 0.00 in the UI).
- The VIEW is grouped by (partner_id, company_id) for multi-company support.
- invoice_date is NOT part of the GROUP BY; instead, we expose invoice_date_min
  and invoice_date_max so the search view can filter using domain on these fields.
  For proper date-range filtering, use the wizard or search filters.
"""

from odoo import api, fields, models
from odoo.tools import SQL


class CustomerArReport(models.Model):
    _name = 'customer.ar.report'
    _description = 'Reporte CxC por Cliente'
    _auto = False
    _rec_name = 'partner_id'
    _order = 'amount_due desc'

    partner_id = fields.Many2one(
        'res.partner', string='Cliente', readonly=True)
    partner_code = fields.Char(
        string='Código - Cliente', readonly=True)
    assigned_salesperson_id = fields.Many2one(
        'res.partner', string='Vendedor', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', readonly=True)
    payment_term_id = fields.Many2one(
        'account.payment.term', string='Plazo de Crédito',
        related='partner_id.property_payment_term_id', readonly=True)
    amount_invoiced = fields.Monetary(
        string='Total Facturado', readonly=True,
        currency_field='currency_id')
    amount_due = fields.Monetary(
        string='Total Pendiente', readonly=True,
        currency_field='currency_id')
    avg_days_to_pay = fields.Float(
        string='Días Promedio de Pago', readonly=True,
        digits=(16, 2), aggregator='avg')
    invoice_count = fields.Integer(
        string='Nº Facturas', readonly=True)
    paid_invoice_count = fields.Integer(
        string='Nº Facturas Pagadas', readonly=True)
    invoice_date_min = fields.Date(
        string='Fecha Factura (Desde)', readonly=True)
    invoice_date_max = fields.Date(
        string='Fecha Factura (Hasta)', readonly=True)

    # -------------------------------------------------------------------------
    # SQL VIEW definition
    # -------------------------------------------------------------------------

    @property
    def _table_query(self) -> SQL:
        return SQL(
            """
            SELECT
                /* Stable unique id per (partner, company) row */
                MIN(am.id)                                          AS id,
                am.partner_id                                       AS partner_id,
                CONCAT(
                    COALESCE(rp.unique_id, ''), ' - ',
                    COALESCE(rp.name, '')
                )                                                   AS partner_code,
                rp.assigned_salesperson_id                          AS assigned_salesperson_id,
                am.company_id                                       AS company_id,
                rc.currency_id                                      AS currency_id,

                /* Totals */
                SUM(am.amount_total_signed)                         AS amount_invoiced,
                SUM(am.amount_residual_signed)                      AS amount_due,

                /* Counts */
                COUNT(am.id)                                        AS invoice_count,
                COUNT(am.id) FILTER (
                    WHERE am.amount_residual = 0
                )                                                   AS paid_invoice_count,

                /* Date boundaries for search filtering */
                MIN(am.invoice_date)                                AS invoice_date_min,
                MAX(am.invoice_date)                                AS invoice_date_max,

                /* Average days to pay — only fully-paid invoices */
                AVG(
                    CASE
                        WHEN am.amount_residual = 0
                             AND pay_dates.last_payment_date IS NOT NULL
                        THEN (pay_dates.last_payment_date - am.invoice_date)
                        ELSE NULL
                    END
                )                                                   AS avg_days_to_pay

            FROM account_move am
            JOIN res_company rc ON rc.id = am.company_id
            JOIN res_partner rp ON rp.id = am.partner_id

            /* Sub-query: last payment date per invoice (only fully paid) */
            LEFT JOIN LATERAL (
                SELECT MAX(apr.max_date) AS last_payment_date
                FROM account_partial_reconcile apr
                JOIN account_move_line aml_inv
                    ON aml_inv.id = apr.debit_move_id
                JOIN account_account aa
                    ON aa.id = aml_inv.account_id
                WHERE aml_inv.move_id = am.id
                  AND aa.account_type = 'asset_receivable'
            ) pay_dates ON am.amount_residual = 0

            WHERE am.move_type = 'out_invoice'
              AND am.state = 'posted'

            GROUP BY
                am.partner_id,
                rp.unique_id,
                rp.name,
                rp.assigned_salesperson_id,
                am.company_id,
                rc.currency_id
            """
        )
