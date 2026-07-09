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
        string='Líneas de Comisión',
        readonly=True,
        copy=False,
    )
    sng_commission_count = fields.Integer(
        string='Comisiones',
        compute='_compute_sng_commission_count',
    )

    @api.depends('sng_commission_line_ids')
    def _compute_sng_commission_count(self):
        for payment in self:
            payment.sng_commission_count = len(payment.sng_commission_line_ids)

    def action_post(self):
        res = super(AccountPayment, self).action_post()
        for payment in self:
            if payment.payment_type == 'inbound' and payment.state == 'posted':
                payment._generate_commission_lines()
        return res

    def action_generate_commission_lines(self):
        """Botón manual para (re)generar líneas de comisión del pago."""
        for payment in self:
            if payment.state != 'posted':
                raise UserError(_(
                    "El pago %(payment)s debe estar publicado para generar comisiones.",
                    payment=payment.name,
                ))
            payment._generate_commission_lines()
        return True

    def _generate_commission_lines(self):
        """Genera o actualiza las líneas de comisión del pago."""
        self.ensure_one()
        if self.payment_type != 'inbound':
            return

        # Eliminamos líneas en borrador para regenerarlas sin duplicados.
        draft_lines = self.sng_commission_line_ids.filtered(lambda l: l.state == 'draft')
        if draft_lines:
            draft_lines.unlink()

        if not self.move_id:
            return

        # Obtenemos los partials reconciliados con facturas de cliente.
        partials_data = self._get_reconciled_invoice_partials()
        if not partials_data:
            return

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

            config = self._get_commission_config(salesperson)
            if not config:
                _logger.info(
                    "No hay configuración de comisión vigente para el vendedor %s en la fecha %s.",
                    salesperson.name, self.date,
                )
                continue

            percentage = config.get_percentage_for_date(self.date)
            if not percentage:
                continue

            invoice_amount_untaxed = invoice.amount_untaxed
            invoice_amount_total = invoice.amount_total
            commission_base = 0.0
            if invoice_amount_total:
                commission_base = amount * (invoice_amount_untaxed / invoice_amount_total)

            commission_amount = commission_base * percentage / 100.0
            if commission_amount <= 0:
                continue

            self.env['sng.commission.payment.line'].create({
                'payment_id': self.id,
                'invoice_id': invoice.id,
                'salesperson_id': salesperson.id,
                'payment_amount': amount,
                'invoice_amount_untaxed': invoice_amount_untaxed,
                'invoice_amount_total': invoice_amount_total,
                'commission_base': commission_base,
                'commission_percentage': percentage,
                'commission_amount': commission_amount,
                'state': 'draft',
            })

    def _get_reconciled_invoice_partials(self):
        """
        Devuelve una lista de tuplas (invoice, partial, amount) con las facturas
        de cliente reconciliadas por este pago y el monto aplicado.
        """
        self.ensure_one()
        result = []
        if not self.move_id:
            return result

        try:
            partials, _exchange_moves = self.move_id._get_reconciled_invoices_partials()
        except Exception:
            # Fallback manual si el helper no aplica directamente al pago.
            partials = []
            for payment_line in self.move_id.line_ids.filtered(
                lambda l: l.account_type == 'asset_receivable'
            ):
                for partial in payment_line.matched_debit_ids | payment_line.matched_credit_ids:
                    invoice_line = (
                        partial.debit_move_id
                        if partial.credit_move_id == payment_line
                        else partial.credit_move_id
                    )
                    partials.append((partial, partial.amount, invoice_line))

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

    def _get_commission_config(self, salesperson):
        """Busca la configuración de comisión vigente para el vendedor y fecha."""
        self.ensure_one()
        domain = [
            ('salesperson_id', '=', salesperson.id),
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
            '|', ('start_date', '=', False), ('start_date', '<=', self.date),
            '|', ('end_date', '=', False), ('end_date', '>=', self.date),
        ]
        return self.env['sng.commission.config'].search(domain, limit=1, order='start_date desc, id desc')
