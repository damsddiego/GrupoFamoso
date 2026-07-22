# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

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
    base_amount = fields.Monetary(
        string='Base Acumulada (sin impuestos)',
        currency_field='currency_id',
        readonly=True,
        help='Suma sin impuestos de los pagos recibidos en el mes.',
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
            ('billed', 'Facturado'),
            ('paid', 'Pagado'),
        ],
        string='Estado',
        compute='_compute_state',
        store=True,
        index=True,
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

    @api.depends('bill_id', 'bill_id.state', 'bill_id.payment_state')
    def _compute_state(self):
        for rec in self:
            bill = rec.bill_id
            if bill and bill.state == 'posted' and bill.payment_state in ('in_payment', 'paid', 'reversed'):
                rec.state = 'paid'
            elif bill and bill.state != 'cancel':
                rec.state = 'billed'
            else:
                rec.state = 'draft'

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
        """Recalcula base, tramo y monto. Solo afecta registros en borrador."""
        Tier = self.env['sng.commission.tier']
        for rec in self:
            if rec.state != 'draft':
                continue
            base = sum(rec.line_ids.mapped('commission_base'))
            tier = Tier.get_tier_for_amount(base, rec.company_id)
            percentage = tier.percentage if tier else 0.0
            rec.write({
                'base_amount': base,
                'tier_id': tier.id if tier else False,
                'percentage': percentage,
                'commission_amount': base * percentage / 100.0,
            })

    def action_view_bill(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.bill_id.id,
        }
