# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class SngCommissionPaymentLine(models.Model):
    _name = 'sng.commission.payment.line'
    _description = 'Detalle de Base de Comisión por Pago'
    _order = 'payment_date desc, id desc'

    name = fields.Char(
        string='Descripción',
        compute='_compute_name',
        store=True,
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Pago',
        required=True,
        index=True,
        ondelete='cascade',
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        index=True,
        ondelete='cascade',
    )
    monthly_id = fields.Many2one(
        'sng.commission.monthly',
        string='Comisión Mensual',
        index=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='payment_id.partner_id',
        store=True,
        index=True,
    )
    salesperson_id = fields.Many2one(
        'res.partner',
        string='Vendedor',
        required=True,
        domain="[('is_salesperson', '=', True)]",
        index=True,
    )
    payment_date = fields.Date(
        string='Fecha de Pago',
        related='payment_id.date',
        store=True,
        index=True,
    )
    period = fields.Date(
        string='Periodo',
        related='monthly_id.period',
        store=True,
        index=True,
        help='Mes en el que esta línea acumula comisión. Puede ser posterior '
             'al mes del pago si aquel ya estaba cerrado.',
    )
    original_period = fields.Date(
        string='Periodo Original',
        compute='_compute_original_period',
        store=True,
        index=True,
        help='Primer día del mes de la fecha del pago.',
    )
    is_rolled_over = fields.Boolean(
        string='Rodado de Otro Mes',
        compute='_compute_is_rolled_over',
        store=True,
        help='Verdadero cuando el pago se acumuló en un mes posterior porque '
             'su mes original ya estaba cerrado.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='payment_id.company_id',
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='payment_id.currency_id',
        store=True,
    )
    payment_amount = fields.Monetary(
        string='Monto del Pago Aplicado',
        currency_field='currency_id',
        required=True,
    )
    invoice_amount_untaxed = fields.Monetary(
        string='Monto Sin Impuestos Factura',
        currency_field='currency_id',
        required=True,
    )
    invoice_amount_total = fields.Monetary(
        string='Monto Total Factura',
        currency_field='currency_id',
        required=True,
    )
    commission_base = fields.Monetary(
        string='Base de Comisión',
        currency_field='currency_id',
        required=True,
        help='Monto sin impuestos pagado proporcionalmente por este pago. '
             'Se acumula en la comisión mensual del vendedor.',
    )
    effective_tax_rate = fields.Float(
        string='% Impuesto Efectivo',
        compute='_compute_tax_profile',
        store=True,
        digits=(16, 1),
        help='Impuesto efectivo de la factura: (total / subtotal - 1) × 100. '
             'Una factura con líneas gravadas y exentas da un porcentaje intermedio.',
    )
    tax_profile = fields.Selection(
        [
            ('taxed_13', 'IVA 13%'),
            ('no_tax', 'Sin impuesto (0%)'),
            ('mixed', 'Tarifa mixta/reducida'),
        ],
        string='Tipo de Factura',
        compute='_compute_tax_profile',
        store=True,
        index=True,
        help='Clasificación según el impuesto efectivo de la factura: 13% completo, '
             'sin impuesto, o intermedio (facturas mixtas o con tarifa reducida).',
    )

    _sql_constraints = [
        (
            'unique_payment_invoice',
            'UNIQUE(payment_id, invoice_id)',
            'Ya existe una línea de comisión para este pago y factura.',
        ),
    ]

    @api.depends('payment_date')
    def _compute_original_period(self):
        for line in self:
            line.original_period = line.payment_date.replace(day=1) if line.payment_date else False

    @api.depends('period', 'original_period')
    def _compute_is_rolled_over(self):
        for line in self:
            line.is_rolled_over = bool(
                line.period and line.original_period and line.period != line.original_period
            )

    @api.depends('invoice_amount_untaxed', 'invoice_amount_total')
    def _compute_tax_profile(self):
        for line in self:
            untaxed = line.invoice_amount_untaxed
            total = line.invoice_amount_total
            if not untaxed or not total:
                line.effective_tax_rate = 0.0
                line.tax_profile = 'no_tax'
                continue
            rate = (total / untaxed - 1.0) * 100.0
            line.effective_tax_rate = rate
            if abs(rate) <= 0.05:
                line.tax_profile = 'no_tax'
            elif abs(rate - 13.0) <= 0.05:
                line.tax_profile = 'taxed_13'
            else:
                line.tax_profile = 'mixed'

    @api.depends('salesperson_id', 'invoice_id', 'commission_base')
    def _compute_name(self):
        for line in self:
            line.name = _(
                "Base %(salesperson)s - Factura %(invoice)s",
                salesperson=line.salesperson_id.name or '',
                invoice=line.invoice_id.name or '',
            )
