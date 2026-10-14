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

    @api.model
    def _sng_period_bounds(self, period):
        """(primer día, último día) del mes de `period`."""
        first = period.replace(day=1)
        return first, first + relativedelta(months=1, days=-1)

    @api.model
    def _sng_find_uncommissioned(self, company, date_from, date_to):
        """Pares (pago, factura) de cobros confirmados en el rango que aún no
        tienen línea de comisión.

        Replica en SQL la lógica de ``account.payment._generate_commission_lines``
        (pago entrante confirmado, conciliado con factura de cliente publicada,
        mes por fecha de confirmación con respaldo en la fecha contable y
        vendedor de la factura, asignado a la factura o asignado al cliente).

        Devuelve una lista de dicts ``{'payment_id', 'invoice_id', 'salesperson_id'}``;
        ``salesperson_id`` es None cuando no hay vendedor resoluble (esos pares
        nunca generan comisión hasta que se asigne un vendedor).
        """
        self.env['account.payment'].flush_model()
        self.env['account.move'].flush_model(['state', 'move_type', 'salesperson_id', 'assigned_salesperson_id', 'sng_commission_exclude'])
        self.env['account.partial.reconcile'].flush_model()
        self.env['sng.commission.payment.line'].flush_model()
        self.env['res.partner'].flush_model(['is_salesperson', 'assigned_salesperson_id'])
        self.env.cr.execute("""
            WITH pays AS (
                SELECT p.id AS pid, p.move_id, p.partner_id
                FROM account_payment p
                JOIN account_move m ON m.id = p.move_id
                WHERE p.payment_type = 'inbound'
                  AND p.state IN ('in_process', 'paid')
                  AND p.company_id = %(company)s
                  AND COALESCE(p.sng_confirmation_date, m.date) BETWEEN %(date_from)s AND %(date_to)s
            ),
            pairs AS (
                SELECT DISTINCT pays.pid, pays.partner_id, inv.id AS inv_id,
                       inv.salesperson_id, inv.assigned_salesperson_id
                FROM pays
                JOIN account_move_line pl ON pl.move_id = pays.move_id
                JOIN account_account aa ON aa.id = pl.account_id AND aa.account_type = 'asset_receivable'
                JOIN account_partial_reconcile pr ON pr.credit_move_id = pl.id OR pr.debit_move_id = pl.id
                JOIN account_move_line il
                  ON il.id = CASE WHEN pr.credit_move_id = pl.id THEN pr.debit_move_id ELSE pr.credit_move_id END
                JOIN account_move inv
                  ON inv.id = il.move_id AND inv.move_type IN ('out_invoice', 'out_refund') AND inv.state = 'posted'
                 AND NOT COALESCE(inv.sng_commission_exclude, FALSE)
            )
            SELECT pr.pid, pr.inv_id,
                   COALESCE(
                     (SELECT sp.id FROM res_partner sp WHERE sp.id = pr.salesperson_id AND sp.is_salesperson),
                     (SELECT sp.id FROM res_partner sp WHERE sp.id = pr.assigned_salesperson_id AND sp.is_salesperson),
                     (SELECT sp.id FROM res_partner sp
                        JOIN res_partner cust ON (cust.assigned_salesperson_id->>%(company_key)s)::int = sp.id
                       WHERE cust.id = pr.partner_id AND sp.is_salesperson)
                   ) AS salesperson_id
            FROM pairs pr
            WHERE NOT EXISTS (
                SELECT 1 FROM sng_commission_payment_line l
                WHERE l.payment_id = pr.pid AND l.invoice_id = pr.inv_id AND l.line_type = 'commission')
            ORDER BY pr.pid, pr.inv_id
        """, {
            'company': company.id,
            'company_key': str(company.id),
            'date_from': date_from,
            'date_to': date_to,
        })
        return [
            {'payment_id': pid, 'invoice_id': inv_id, 'salesperson_id': sp_id}
            for pid, inv_id, sp_id in self.env.cr.fetchall()
        ]

    @api.model
    def _sng_generate_pending(self, company, date_from, date_to):
        """Genera las líneas de comisión que faltan para los cobros confirmados
        en el rango. Devuelve los pagos procesados."""
        rows = self._sng_find_uncommissioned(company, date_from, date_to)
        payment_ids = sorted({r['payment_id'] for r in rows if r['salesperson_id']})
        payments = self.env['account.payment'].sudo().browse(payment_ids)
        for payment in payments:
            payment._generate_commission_lines()
        if payments:
            _logger.info(
                "Comisiones pendientes generadas para %s (%s → %s): %s pagos.",
                company.name, date_from, date_to, len(payments),
            )
        return payments

    def action_close(self):
        """Genera las comisiones pendientes del mes, recalcula y cierra: deja
        de aceptar cambios; los pagos tardíos de este periodo se acumularán
        en el siguiente mes abierto."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Solo se pueden cerrar comisiones en estado Pendiente (%(name)s está en %(state)s).",
                    name=rec.name, state=dict(rec._fields['state']._description_selection(rec.env)).get(rec.state),
                ))
        # Antes de cerrar, los cobros del mes que aún no tienen línea (p. ej.
        # conciliados después de confirmarse) se generan para que entren a
        # este mes y no rueden al siguiente.
        for company, period in {(rec.company_id, rec.period) for rec in self}:
            first, last = self._sng_period_bounds(period)
            self._sng_generate_pending(company, first, last)
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
