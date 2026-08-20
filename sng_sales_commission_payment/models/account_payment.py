# -*- coding: utf-8 -*-

import logging

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CR_TZ = pytz.timezone('America/Costa_Rica')


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    sng_confirmation_date = fields.Date(
        string='Fecha de Confirmación',
        copy=False,
        readonly=True,
        index=True,
        help='Día (hora de Costa Rica) en que el pago pasó por primera vez a '
             'En proceso/Pagado. Determina el mes de la comisión.',
    )
    sng_commission_line_ids = fields.One2many(
        'sng.commission.payment.line',
        'payment_id',
        string='Detalle de Comisión',
        readonly=True,
        copy=False,
        groups='sales_commission_omax.group_sales_commission_user',
    )
    sng_commission_count = fields.Integer(
        string='Comisiones',
        compute='_compute_sng_commission_count',
        groups='sales_commission_omax.group_sales_commission_user',
    )

    @api.depends('sng_commission_line_ids')
    def _compute_sng_commission_count(self):
        for payment in self:
            payment.sng_commission_count = len(payment.sng_commission_line_ids)

    # Estados de account.payment (Odoo 18) en los que el pago está confirmado.
    SNG_COMMISSION_VALID_STATES = ('in_process', 'paid')

    @api.model
    def _sng_confirmation_today(self):
        """Fecha actual en hora de Costa Rica, independiente del tz del usuario."""
        return fields.Datetime.now().replace(tzinfo=pytz.utc).astimezone(CR_TZ).date()

    def _sng_set_confirmation_date(self):
        """Sella la fecha de la PRIMERA confirmación; reconfirmar no la mueve."""
        to_stamp = self.filtered(
            lambda p: p.state in self.SNG_COMMISSION_VALID_STATES and not p.sng_confirmation_date
        )
        if to_stamp:
            to_stamp.write({'sng_confirmation_date': self._sng_confirmation_today()})

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        # Pagos que nacen ya confirmados (p. ej. conciliación bancaria).
        payments._sng_set_confirmation_date()
        return payments

    def write(self, vals):
        res = super().write(vals)
        # action_post y la app asignan el estado vía write; el write interno de
        # _sng_set_confirmation_date no incluye 'state', así que no hay recursión.
        if vals.get('state') in self.SNG_COMMISSION_VALID_STATES:
            self._sng_set_confirmation_date()
        return res

    def action_post(self):
        res = super(AccountPayment, self).action_post()
        for payment in self:
            if payment.payment_type == 'inbound' and payment.state in self.SNG_COMMISSION_VALID_STATES:
                payment._generate_commission_lines()
        return res

    def action_draft(self):
        self._sng_handle_payment_invalidation('canceled')
        return super().action_draft()

    def action_cancel(self):
        self._sng_handle_payment_invalidation('canceled')
        return super().action_cancel()

    def action_reject(self):
        self._sng_handle_payment_invalidation('canceled')
        return super().action_reject()

    def _sng_handle_payment_invalidation(self, reason, invoices=None):
        """Al invalidarse un pago (anulado/cancelado/rechazado/desconciliado):

        - sus líneas de comisión en meses en borrador se eliminan y el mes se
          recalcula;
        - las de meses cerrados/facturados/pagados generan un reverso en el mes
          abierto actual por lo que realmente se pagó (idempotente).

        Con ``invoices`` solo se afectan las líneas de esas facturas (caso
        desconciliación parcial).
        """
        Line = self.env['sng.commission.payment.line'].sudo()
        domain = [('payment_id', 'in', self.ids), ('line_type', '=', 'commission')]
        if invoices is not None:
            domain.append(('invoice_id', 'in', invoices.ids))
        lines = Line.search(domain)
        if not lines:
            return
        draft_lines = lines.filtered(lambda l: l.monthly_id.state == 'draft')
        frozen_lines = lines - draft_lines
        monthlies = draft_lines.mapped('monthly_id')
        draft_lines.unlink()
        monthlies._recompute_commission()
        frozen_lines._create_reversals(reason)

    def action_generate_commission_lines(self):
        """Botón manual para (re)generar el detalle de comisión del pago."""
        for payment in self:
            if payment.state not in self.SNG_COMMISSION_VALID_STATES:
                raise UserError(_(
                    "El pago %(payment)s debe estar confirmado para generar comisiones.",
                    payment=payment.name,
                ))
            payment._generate_commission_lines()
        return True

    def _generate_commission_lines(self):
        """Genera/actualiza el detalle de base y recalcula la comisión mensual."""
        self.ensure_one()
        if (
            self.payment_type != 'inbound'
            or self.state not in self.SNG_COMMISSION_VALID_STATES
            or not self.move_id
            or not self.date
        ):
            return

        partials_data = self._get_reconciled_invoice_partials()
        if not partials_data:
            return

        # sudo: cualquier usuario de contabilidad puede postear un cobro sin
        # tener permisos sobre los modelos de comisión.
        Monthly = self.env['sng.commission.monthly'].sudo()
        Line = self.env['sng.commission.payment.line'].sudo()
        # El mes de la comisión lo define la fecha de confirmación del pago;
        # la fecha contable solo es respaldo para pagos antiguos sin sellar.
        period = (self.sng_confirmation_date or self.date).replace(day=1)
        affected = Monthly

        for invoice, partial, amount in partials_data:
            if invoice.move_type not in ('out_invoice', 'out_refund') or invoice.state != 'posted':
                continue

            salesperson = self._get_salesperson_for_commission(invoice)
            if not salesperson:
                _logger.info(
                    "No se encontró vendedor para la factura %s y pago %s; se omite comisión.",
                    invoice.name, self.name,
                )
                continue

            invoice_amount_untaxed = invoice.amount_untaxed
            invoice_amount_total = invoice.amount_total
            commission_base = 0.0
            if invoice_amount_total:
                commission_base = amount * (invoice_amount_untaxed / invoice_amount_total)
            if commission_base <= 0:
                continue

            existing = Line.search([
                ('payment_id', '=', self.id),
                ('invoice_id', '=', invoice.id),
                ('line_type', '=', 'commission'),
            ], limit=1)
            # Una línea que ya quedó en un mes cerrado/facturado no se toca.
            if existing and existing.monthly_id.state != 'draft':
                # Pago revivido tras un reverso: si el reverso sigue en un mes
                # abierto se elimina y la comisión original vuelve a valer.
                reversals = existing.reversal_line_ids.filtered(
                    lambda r: r.monthly_id.state == 'draft')
                if reversals:
                    reversal_months = reversals.mapped('monthly_id')
                    reversals.unlink()
                    affected |= reversal_months
                continue

            vals = {
                'salesperson_id': salesperson.id,
                'payment_amount': amount,
                'invoice_amount_untaxed': invoice_amount_untaxed,
                'invoice_amount_total': invoice_amount_total,
                'commission_base': commission_base,
            }
            if existing:
                existing.write(vals)
                affected |= existing.monthly_id
                continue

            # Si el mes natural del pago ya está cerrado, la comisión se
            # acumula en el siguiente mes abierto del vendedor.
            open_period = Monthly._get_open_period(salesperson, self.company_id, period)
            if not open_period:
                continue
            if open_period != period:
                _logger.info(
                    "Pago %s (factura %s): mes %s cerrado; la comisión se acumula en %s.",
                    self.name, invoice.name, period, open_period,
                )
            monthly = Monthly._get_or_create(salesperson, self.company_id, open_period)
            Line.create(dict(vals, monthly_id=monthly.id, payment_id=self.id, invoice_id=invoice.id))
            affected |= monthly

        affected._recompute_commission()

    def _get_reconciled_invoice_partials(self):
        """
        Devuelve una lista de tuplas (invoice, partial, amount) con las facturas
        de cliente reconciliadas por este pago y el monto aplicado.
        """
        self.ensure_one()
        result = []
        if not self.move_id:
            return result

        partials, _exchange_moves = self.move_id._get_reconciled_invoices_partials()

        seen = set()
        for partial, amount, invoice_line in partials:
            invoice = invoice_line.move_id
            if invoice.id in seen:
                continue
            seen.add(invoice.id)
            result.append((invoice, partial, amount))
        return result

    def _get_salesperson_for_commission(self, invoice):
        """Resuelve el vendedor a usar para la comisión de una factura."""
        self.ensure_one()
        candidates = []
        if invoice.salesperson_id and invoice.salesperson_id.is_salesperson:
            candidates.append(invoice.salesperson_id)
        if invoice.assigned_salesperson_id and invoice.assigned_salesperson_id.is_salesperson:
            candidates.append(invoice.assigned_salesperson_id)
        if self.partner_id:
            assigned = self.partner_id.with_company(self.company_id).assigned_salesperson_id
            if assigned and assigned.is_salesperson:
                candidates.append(assigned)
        # Preferimos el vendedor de la factura; si no, el asignado al cliente.
        for candidate in candidates:
            return candidate
        return False
