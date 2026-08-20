# -*- coding: utf-8 -*-

import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MONTH_NAMES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


class SngCommissionMonthly(models.Model):
    _name = 'sng.commission.monthly'
    _description = 'Comisión Mensual por Vendedor'
    _order = 'period desc, salesperson_id'

    name = fields.Char(
        string='Descripción',
        compute='_compute_name',
        store=True,
    )
    salesperson_id = fields.Many2one(
        'res.partner',
        string='Vendedor',
        required=True,
        domain="[('is_salesperson', '=', True)]",
        index=True,
    )
    period = fields.Date(
        string='Periodo',
        required=True,
        index=True,
        help='Primer día del mes al que corresponde la comisión.',
    )
    period_label = fields.Char(
        string='Mes',
        compute='_compute_period_label',
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Moneda',
    )
    line_ids = fields.One2many(
        'sng.commission.payment.line',
        'monthly_id',
        string='Detalle de Pagos',
        readonly=True,
    )
    commission_line_ids = fields.One2many(
        'sng.commission.payment.line',
        'monthly_id',
        string='Detalle de Pagos (comisión)',
        domain=[('line_type', '=', 'commission')],
        readonly=True,
    )
    reversal_line_ids = fields.One2many(
        'sng.commission.payment.line',
        'monthly_id',
        string='Reversos',
        domain=[('line_type', '=', 'reversal')],
        readonly=True,
    )
    base_amount = fields.Monetary(
        string='Base Acumulada (sin impuestos)',
        currency_field='currency_id',
        readonly=True,
        help='Suma sin impuestos de los pagos recibidos en el mes.',
    )
    adjustment_amount = fields.Monetary(
        string='Reversos del Mes',
        currency_field='currency_id',
        readonly=True,
        help='Total (negativo) descontado por comisiones ya pagadas de pagos '
             'cancelados o desconciliados de meses cerrados. No afecta la base '
             'ni el tramo: se resta directo del monto de comisión.',
    )
    tier_id = fields.Many2one(
        'sng.commission.tier',
        string='Tramo Aplicado',
        readonly=True,
    )
    percentage = fields.Float(
        string='% Comisión',
        readonly=True,
    )
    commission_amount = fields.Monetary(
        string='Monto de Comisión',
        currency_field='currency_id',
        readonly=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Pendiente'),
            ('closed', 'Cerrado'),
            ('billed', 'Facturado'),
            ('paid', 'Pagado'),
        ],
        string='Estado',
        compute='_compute_state',
        store=True,
        index=True,
    )
    closed = fields.Boolean(
        string='Mes Cerrado',
        copy=False,
        help='Un mes cerrado ya no se recalcula: los pagos que lleguen después '
             'con fecha de este mes se acumulan en el siguiente mes abierto.',
    )
    closed_date = fields.Datetime(
        string='Fecha de Cierre',
        copy=False,
        readonly=True,
    )
    closed_by_id = fields.Many2one(
        'res.users',
        string='Cerrado por',
        copy=False,
        readonly=True,
    )
    bill_id = fields.Many2one(
        'account.move',
        string='Factura de Comisión',
        index=True,
        ondelete='set null',
        copy=False,
    )

    _sql_constraints = [
        (
            'unique_salesperson_period_company',
            'UNIQUE(salesperson_id, period, company_id)',
            'Ya existe una comisión mensual para este vendedor y periodo.',
        ),
    ]

    @api.depends('salesperson_id', 'period_label')
    def _compute_name(self):
        for rec in self:
            rec.name = _(
                "Comisión %(salesperson)s - %(period)s",
                salesperson=rec.salesperson_id.name or '',
                period=rec.period_label or '',
            )

    @api.depends('period')
    def _compute_period_label(self):
        for rec in self:
            if rec.period:
                rec.period_label = "%s %s" % (MONTH_NAMES.get(rec.period.month, ''), rec.period.year)
            else:
                rec.period_label = ''

    @api.depends('bill_id', 'bill_id.state', 'bill_id.payment_state', 'closed')
    def _compute_state(self):
        for rec in self:
            bill = rec.bill_id
            if bill and bill.state == 'posted' and bill.payment_state in ('in_payment', 'paid', 'reversed'):
                rec.state = 'paid'
            elif bill and bill.state != 'cancel':
                rec.state = 'billed'
            elif rec.closed:
                rec.state = 'closed'
            else:
                rec.state = 'draft'

    def action_close(self):
        """Recalcula y cierra el mes: deja de aceptar cambios; los pagos
        tardíos de este periodo se acumularán en el siguiente mes abierto."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Solo se pueden cerrar comisiones en estado Pendiente (%(name)s está en %(state)s).",
                    name=rec.name, state=dict(rec._fields['state']._description_selection(rec.env)).get(rec.state),
                ))
        self._recompute_commission()
        self.write({
            'closed': True,
            'closed_date': fields.Datetime.now(),
            'closed_by_id': self.env.user.id,
        })
        return True

    def action_reopen(self):
        """Reabre un mes cerrado sin factura y lo recalcula.

        Las líneas que ya rodaron a otro mes por estar este cerrado NO
        regresan: permanecen en el mes donde se acumularon.
        """
        for rec in self:
            if rec.state != 'closed':
                raise UserError(_(
                    "Solo se pueden reabrir comisiones cerradas (%(name)s).",
                    name=rec.name,
                ))
            if rec.bill_id and rec.bill_id.state != 'cancel':
                raise UserError(_(
                    "No se puede reabrir %(name)s: ya tiene la factura %(bill)s.",
                    name=rec.name, bill=rec.bill_id.name,
                ))
        self.write({
            'closed': False,
            'closed_date': False,
            'closed_by_id': False,
        })
        self._recompute_commission()
        return True

    @api.model
    def _get_open_period(self, salesperson, company, period):
        """Devuelve el primer periodo >= period cuyo mensual del vendedor no
        esté cerrado/facturado (o no exista). Máximo 24 meses hacia adelante."""
        current = period
        for _i in range(24):
            monthly = self.search([
                ('salesperson_id', '=', salesperson.id),
                ('company_id', '=', company.id),
                ('period', '=', current),
            ], limit=1)
            if not monthly or monthly.state == 'draft':
                return current
            current = current + relativedelta(months=1)
        _logger.warning(
            "No se encontró un periodo abierto para %s en %s partiendo de %s; se omite la comisión.",
            salesperson.name, company.name, period,
        )
        return False

    @api.model
    def _get_or_create(self, salesperson, company, period):
        """Devuelve (creando si no existe) el registro mensual del vendedor."""
        rec = self.search([
            ('salesperson_id', '=', salesperson.id),
            ('company_id', '=', company.id),
            ('period', '=', period),
        ], limit=1)
        if not rec:
            rec = self.create({
                'salesperson_id': salesperson.id,
                'company_id': company.id,
                'period': period,
            })
        return rec

    def _recompute_commission(self):
        """Recalcula base, tramo y monto. Solo afecta registros en borrador.

        Los reversos no suman base (no cambian el tramo): su ajuste monetario
        se descuenta directo del monto de comisión del mes.
        """
        Tier = self.env['sng.commission.tier']
        for rec in self:
            if rec.state != 'draft':
                continue
            base = sum(rec.line_ids.filtered(
                lambda l: l.line_type == 'commission').mapped('commission_base'))
            adjustment = sum(rec.line_ids.mapped('commission_adjustment'))
            tier = Tier.get_tier_for_amount(base, rec.company_id)
            percentage = tier.percentage if tier else 0.0
            rec.write({
                'base_amount': base,
                'tier_id': tier.id if tier else False,
                'percentage': percentage,
                'adjustment_amount': adjustment,
                'commission_amount': base * percentage / 100.0 + adjustment,
            })

    def _get_tax_profile_summary(self):
        """Resumen por tipo de factura para los reportes PDF/XLSX."""
        self.ensure_one()
        Line = self.env['sng.commission.payment.line']
        labels = dict(Line._fields['tax_profile']._description_selection(self.env))
        summary = []
        for profile in ('taxed_13', 'no_tax', 'mixed'):
            lines = self.line_ids.filtered(
                lambda l: l.tax_profile == profile and l.line_type == 'commission')
            if not lines:
                continue
            summary.append({
                'label': labels.get(profile, profile),
                'count': len(lines),
                'payment_amount': sum(lines.mapped('payment_amount')),
                'commission_base': sum(lines.mapped('commission_base')),
            })
        return summary

    def action_view_bill(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.bill_id.id,
        }
