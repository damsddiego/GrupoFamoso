# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

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

    def action_post(self):
        res = super(AccountPayment, self).action_post()
        for payment in self:
            if payment.payment_type == 'inbound' and payment.state in self.SNG_COMMISSION_VALID_STATES:
                payment._generate_commission_lines()
        return res

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
        period = self.date.replace(day=1)
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

            monthly = Monthly._get_or_create(salesperson, self.company_id, period)
            # No modificamos meses ya facturados o pagados.
            if monthly.state != 'draft':
                continue

            vals = {
                'monthly_id': monthly.id,
                'salesperson_id': salesperson.id,
                'payment_amount': amount,
                'invoice_amount_untaxed': invoice_amount_untaxed,
                'invoice_amount_total': invoice_amount_total,
                'commission_base': commission_base,
            }
            existing = Line.search([
                ('payment_id', '=', self.id),
                ('invoice_id', '=', invoice.id),
            ], limit=1)
            if existing:
                existing.write(vals)
            else:
                Line.create(dict(vals, payment_id=self.id, invoice_id=invoice.id))
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
