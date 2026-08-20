# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


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
    confirmation_date = fields.Date(
        string='Fecha de Confirmación',
        related='payment_id.sng_confirmation_date',
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
        help='Primer día del mes de la confirmación del pago (o de su fecha '
             'contable si no hay fecha de confirmación).',
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
    line_type = fields.Selection(
        [
            ('commission', 'Comisión'),
            ('reversal', 'Reverso'),
        ],
        string='Tipo de Línea',
        required=True,
        default='commission',
        index=True,
        help='Un reverso descuenta la comisión ya pagada de un pago que fue '
             'cancelado o desconciliado después de cerrar su mes.',
    )
    commission_adjustment = fields.Monetary(
        string='Ajuste de Comisión',
        currency_field='currency_id',
        default=0.0,
        help='Monto (negativo) que se descuenta de la comisión del mes: lo que '
             'realmente se pagó por el pago revertido (base × % del mes original). '
             'No afecta la base ni el tramo del mes donde se descuenta.',
    )
    reversal_of_line_id = fields.Many2one(
        'sng.commission.payment.line',
        string='Reverso de',
        index=True,
        ondelete='set null',
        help='Línea de comisión original (de un mes cerrado) que este reverso descuenta.',
    )
    reversal_line_ids = fields.One2many(
        'sng.commission.payment.line',
        'reversal_of_line_id',
        string='Reversos Generados',
    )
    reversal_reason = fields.Selection(
        [
            ('canceled', 'Pago cancelado/anulado'),
            ('unreconciled', 'Pago desconciliado de la factura'),
        ],
        string='Motivo del Reverso',
    )
    original_monthly_id = fields.Many2one(
        'sng.commission.monthly',
        string='Mes Original del Reverso',
        related='reversal_of_line_id.monthly_id',
        store=True,
        help='Mes cerrado donde se pagó la comisión que este reverso descuenta.',
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
            'UNIQUE(payment_id, invoice_id, line_type)',
            'Ya existe una línea de comisión (o reverso) para este pago y factura.',
        ),
    ]

    @api.depends('confirmation_date', 'payment_date')
    def _compute_original_period(self):
        for line in self:
            base_date = line.confirmation_date or line.payment_date
            line.original_period = base_date.replace(day=1) if base_date else False

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

    @api.depends('salesperson_id', 'invoice_id', 'commission_base', 'line_type')
    def _compute_name(self):
        for line in self:
            if line.line_type == 'reversal':
                line.name = _(
                    "Reverso %(salesperson)s - Factura %(invoice)s",
                    salesperson=line.salesperson_id.name or '',
                    invoice=line.invoice_id.name or '',
                )
            else:
                line.name = _(
                    "Base %(salesperson)s - Factura %(invoice)s",
                    salesperson=line.salesperson_id.name or '',
                    invoice=line.invoice_id.name or '',
                )

    def _create_reversals(self, reason):
        """Crea un reverso en el mes abierto actual por cada línea de comisión
        cuyo mes ya está cerrado/facturado/pagado.

        El reverso descuenta exactamente lo que se pagó (base × % del mes
        original) como ajuste monetario: no toca la base ni el tramo del mes
        donde se descuenta. Idempotente: si la línea ya tiene un reverso no se
        crea otro.
        """
        Monthly = self.env['sng.commission.monthly'].sudo()
        Line = self.env['sng.commission.payment.line'].sudo()
        start_period = self.env['account.payment']._sng_confirmation_today().replace(day=1)
        for line in self:
            if line.line_type != 'commission' or line.monthly_id.state == 'draft':
                continue
            if line.reversal_line_ids:
                continue
            paid_amount = line.commission_base * (line.monthly_id.percentage or 0.0) / 100.0
            if line.currency_id.is_zero(paid_amount):
                # El mes original no alcanzó tramo: no se pagó nada por esta línea.
                continue
            open_period = Monthly._get_open_period(line.salesperson_id, line.company_id, start_period)
            if not open_period:
                _logger.warning(
                    "Sin mes abierto para revertir la comisión del pago %s (vendedor %s); "
                    "el reverso queda pendiente de crear manualmente.",
                    line.payment_id.name, line.salesperson_id.name,
                )
                continue
            monthly = Monthly._get_or_create(line.salesperson_id, line.company_id, open_period)
            Line.create({
                'line_type': 'reversal',
                'reversal_of_line_id': line.id,
                'reversal_reason': reason,
                'monthly_id': monthly.id,
                'payment_id': line.payment_id.id,
                'invoice_id': line.invoice_id.id,
                'salesperson_id': line.salesperson_id.id,
                'payment_amount': -line.payment_amount,
                'invoice_amount_untaxed': line.invoice_amount_untaxed,
                'invoice_amount_total': line.invoice_amount_total,
                'commission_base': 0.0,
                'commission_adjustment': -paid_amount,
            })
            monthly._recompute_commission()
