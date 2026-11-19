# -*- coding: utf-8 -*-

import re

from odoo import models, _

# Zona horaria del negocio: la fecha de confirmación del pago se guarda en
# hora de Costa Rica, así que la fecha de la nota de crédito se compara igual.
SNG_TZ = 'America/Costa_Rica'


class SngCommissionMonthly(models.Model):
    _inherit = 'sng.commission.monthly'

    # ------------------------------------------------------------------
    # 1. De dónde salen los pagos + cuadre con el monto del módulo
    # ------------------------------------------------------------------

    @staticmethod
    def _sng_normalize_name(name):
        return re.sub(r'\s+', ' ', (name or '').strip().upper())

    def _sng_payment_origin(self, payment):
        """(orden, etiqueta) del origen de un pago para el análisis.

        La tableta "del vendedor" se reconoce por el contacto que manda la app
        o por el mismo nombre: hay vendedores con dos contactos duplicados y
        la app manda cualquiera de los dos.
        """
        self.ensure_one()
        if payment.sng_from_app and payment.sng_origen == 'ruteros':
            seller = payment.sng_vendedor_id
            if seller and (
                seller == self.salesperson_id
                or self._sng_normalize_name(seller.name) == self._sng_normalize_name(self.salesperson_id.name)
            ):
                return 0, _('Tableta del vendedor')
            return 1, _('Otra tableta: %(name)s', name=seller.name or _('sin vendedor'))
        if payment.sng_from_app and payment.sng_origen == 'escritorio':
            return 2, _('App de escritorio (oficina)')
        return 3, _('Registrado en Odoo: %(user)s', user=payment.create_uid.name or '')

    def _sng_analysis_origin(self):
        """Pagos del mes agrupados por origen y cuadre base × % − reversos."""
        self.ensure_one()
        self = self.sudo()  # el mensual completo, sean cuales sean las compañías activas
        groups = {}
        for line in self.commission_line_ids:
            key = self._sng_payment_origin(line.payment_id)
            group = groups.setdefault(key, {'payments': set(), 'payment_amount': 0.0, 'commission_base': 0.0})
            group['payments'].add(line.payment_id.id)
            group['payment_amount'] += line.payment_amount
            group['commission_base'] += line.commission_base
        rows = [
            {
                'label': label,
                'payment_count': len(group['payments']),
                'payment_amount': group['payment_amount'],
                'commission_base': group['commission_base'],
            }
            for (_rank, label), group in sorted(groups.items())
        ]

        reversals = self.reversal_line_ids
        base = sum(row['commission_base'] for row in rows)
        gross = self.currency_id.round(base * self.percentage / 100.0)
        adjustment = sum(self.line_ids.mapped('commission_adjustment'))
        computed = self.currency_id.round(gross + adjustment)
        return {
            'groups': rows,
            'reversals': {
                'payment_count': len(reversals.mapped('payment_id')),
                'payment_amount': sum(reversals.mapped('payment_amount')),
                'commission_adjustment': sum(reversals.mapped('commission_adjustment')),
            },
            'check': {
                'base': base,
                'percentage': self.percentage,
                'gross': gross,
                'adjustment': adjustment,
                'computed': computed,
                'module': self.commission_amount,
                'difference': self.currency_id.round(computed - self.commission_amount),
            },
        }

    # ------------------------------------------------------------------
    # 2. Notas de crédito sobre facturas ya cobradas
    # ------------------------------------------------------------------

    def _sng_analysis_credit_notes(self):
        """Notas de crédito publicadas que se hicieron sobre facturas cobradas
        en este mes, el día del pago o después, y en qué terminaron.

        La comisión es sobre lo cobrado, así que una nota de crédito no genera
        por sí sola comisión de más: si se aplica a una factura (la misma u
        otra), esa parte se salda sin pago y nunca comisiona; si queda sin
        aplicar es saldo a favor del cliente. Solo lo que se le DEVUELVE en
        efectivo al cliente es comisión pagada de más (dinero cobrado y
        comisionado que se regresó). Si para aplicar la nota se desconcilia el
        pago, el módulo ya crea el reverso (ver reversos del mes).
        """
        self.ensure_one()
        self = self.sudo()  # el mensual completo, sean cuales sean las compañías activas
        for model in ('sng.commission.payment.line', 'account.move', 'account.move.line',
                      'account.partial.reconcile', 'account.payment'):
            self.env[model].flush_model()
        self.env.cr.execute("""
            WITH lines AS (
                SELECT l.invoice_id,
                       MIN(COALESCE(l.confirmation_date, l.payment_date)) AS conf,
                       SUM(l.commission_base) AS base
                FROM sng_commission_payment_line l
                WHERE l.monthly_id = %(monthly)s AND l.line_type = 'commission'
                GROUP BY l.invoice_id
            )
            SELECT nc.id AS nc_id, ln.invoice_id, ln.conf, ln.base,
                   (SELECT SUM(a.commission_base) FROM sng_commission_payment_line a
                     WHERE a.invoice_id = ln.invoice_id AND a.line_type = 'commission') AS base_all,
                   (nc.create_date AT TIME ZONE 'UTC' AT TIME ZONE %(tz)s)::date AS nc_date,
                   ABS(nc.amount_untaxed_signed) AS nc_untaxed,
                   ABS(nc.amount_total_signed) AS nc_total,
                   ABS(nc.amount_residual_signed) AS nc_residual
            FROM lines ln
            JOIN account_move nc
              ON nc.reversed_entry_id = ln.invoice_id
             AND nc.move_type = 'out_refund' AND nc.state = 'posted'
            WHERE (nc.create_date AT TIME ZONE 'UTC' AT TIME ZONE %(tz)s)::date >= ln.conf
            ORDER BY nc_date, nc.id
        """, {'monthly': self.id, 'tz': SNG_TZ})
        records = self.env.cr.dictfetchall()

        # Contra qué se concilió cada nota: facturas, devolución de dinero
        # (pago saliente o línea de extracto) u otro asiento.
        applied = {}
        if records:
            self.env.cr.execute("""
                SELECT nl.move_id AS nc_id,
                       CASE WHEN om.move_type = 'out_invoice' THEN 'invoices'
                            WHEN p.payment_type = 'outbound' OR om.statement_line_id IS NOT NULL THEN 'refunded'
                            ELSE 'other' END AS kind,
                       SUM(pr.amount) AS amount
                FROM account_move_line nl
                JOIN account_account aa ON aa.id = nl.account_id AND aa.account_type = 'asset_receivable'
                JOIN account_partial_reconcile pr ON pr.credit_move_id = nl.id OR pr.debit_move_id = nl.id
                JOIN account_move_line ol
                  ON ol.id = CASE WHEN pr.credit_move_id = nl.id THEN pr.debit_move_id ELSE pr.credit_move_id END
                JOIN account_move om ON om.id = ol.move_id
                LEFT JOIN account_payment p ON p.id = om.origin_payment_id
                WHERE nl.move_id IN %(ncs)s
                GROUP BY nl.move_id, kind
            """, {'ncs': tuple(rec['nc_id'] for rec in records)})
            for nc_id, kind, amount in self.env.cr.fetchall():
                applied.setdefault(nc_id, {})[kind] = float(amount)

        Move = self.env['account.move']
        remaining = {}
        rows = []
        for rec in records:
            dest = applied.get(rec['nc_id'], {})
            refunded = dest.get('refunded', 0.0)
            total = float(rec['nc_total'])
            # Sin IVA de lo devuelto. Si la factura se cobró en varios meses,
            # a este mes le toca su parte de la base; tope en esa base.
            refunded_untaxed = refunded * float(rec['nc_untaxed']) / total if total else 0.0
            base_all = float(rec['base_all'] or 0.0)
            refunded_untaxed *= float(rec['base']) / base_all if base_all else 0.0
            left = remaining.setdefault(rec['invoice_id'], float(rec['base']))
            refunded_untaxed = self.currency_id.round(max(min(refunded_untaxed, left), 0.0))
            remaining[rec['invoice_id']] = left - refunded_untaxed
            credit_note = Move.browse(rec['nc_id'])
            invoice = Move.browse(rec['invoice_id'])
            rows.append({
                'credit_note': credit_note.name,
                'reason': (credit_note.ref or '').split(',')[-1].strip() if credit_note.ref else '',
                'invoice': invoice.name,
                'partner': invoice.partner_id.name,
                'credit_note_date': rec['nc_date'],
                'confirmation_date': rec['conf'],
                'total': total,
                'to_invoices': dest.get('invoices', 0.0),
                'unapplied': float(rec['nc_residual']),
                'refunded': refunded,
                'other': dest.get('other', 0.0),
                'overpaid': self.currency_id.round(refunded_untaxed * self.percentage / 100.0),
            })
        return {
            'rows': rows,
            'credit_note_count': len(rows),
            'total': sum(row['total'] for row in rows),
            'to_invoices': sum(row['to_invoices'] for row in rows),
            'unapplied': sum(row['unapplied'] for row in rows),
            'refunded': sum(row['refunded'] for row in rows),
            'other': sum(row['other'] for row in rows),
            'overpaid': sum(row['overpaid'] for row in rows),
        }

    # ------------------------------------------------------------------
    # 3. Cobros de meses anteriores que entraron en este mes
    # ------------------------------------------------------------------

    def _sng_original_percentage(self, company, period):
        """% que tuvo este vendedor en el mes ``period`` para la compañía: el
        del mensual de ese mes cuyo cuadro la incluye. None si no tuvo mensual
        (sin % real contra el cual comparar)."""
        self.ensure_one()
        monthly = self.sudo().search([
            ('salesperson_id', '=', self.salesperson_id.id),
            ('scheme_id.company_ids', 'in', company.ids),
            ('period', '=', period.replace(day=1)),
        ], limit=1)
        return monthly.percentage if monthly else None

    def _sng_analysis_prior_collections(self):
        """Pagos con fecha de un mes anterior que se comisionaron en este mes,
        porque se confirmaron tarde o porque su mes ya estaba cerrado. Compara
        el % de este mes con el que tuvo el vendedor en el mes original.

        Un recibo de la tableta que llegó tarde con fecha de este mes no se
        detecta: Odoo no conoce la fecha de la tableta. Si el vendedor no tuvo
        mensual en el mes original, ``original_percentage`` es None y no hay
        diferencia que calcular.
        """
        self.ensure_one()
        self = self.sudo()  # el mensual completo, sean cuales sean las compañías activas
        first = self.period.replace(day=1)
        lines = self.commission_line_ids.filtered(
            lambda l: l.is_rolled_over or (l.payment_date and l.payment_date < first))
        percentages = {}
        rows = []
        for line in lines.sorted(lambda l: (l.payment_date or first, l.payment_id.id, l.id)):
            if line.is_rolled_over and line.original_period:
                original = line.original_period
                reason = _('Rodó: su mes ya estaba cerrado')
            else:
                original = line.payment_date.replace(day=1)
                reason = _('Confirmado tarde')
            key = (line.company_id, original)
            if key not in percentages:
                percentages[key] = self._sng_original_percentage(line.company_id, original)
            original_pct = percentages[key]
            has_original = original_pct is not None
            rows.append({
                'payment': line.payment_id.name,
                'receipt': line.sng_numero_recibo or line.payment_id.memo or '',
                'partner': line.partner_id.name,
                'invoice': line.invoice_id.name,
                'payment_date': line.payment_date,
                'confirmation_date': line.confirmation_date,
                'reason': reason,
                'commission_base': line.commission_base,
                'commission': self.currency_id.round(line.commission_base * self.percentage / 100.0),
                'original_percentage': original_pct,
                'difference': self.currency_id.round(
                    line.commission_base * (original_pct - self.percentage) / 100.0) if has_original else 0.0,
            })
        return {
            'rows': rows,
            'payment_count': len(lines.mapped('payment_id')),
            'commission_base': sum(row['commission_base'] for row in rows),
            'commission': sum(row['commission'] for row in rows),
            'difference': sum(row['difference'] for row in rows),
        }

    # ------------------------------------------------------------------
    # 4. Reversos que no se devolvieron
    # ------------------------------------------------------------------

    def _sng_analysis_unreturned_reversals(self):
        """Reversos del mes cuyo pago se volvió a aplicar a una factura (en el
        mismo movimiento o después) sin generar comisión nueva.

        Si se reaplicó a la misma factura, el vendedor perdió esa comisión y el
        botón "Generar comisiones" no la recupera (ya existe la línea del mes
        original). Si fue a otra factura, "Generar comisiones" crea la línea
        para el vendedor de esa factura, que puede ser otro: en ese caso el
        reverso de este vendedor es correcto y no suma.

        "No devuelto" es la parte del reverso que corresponde a lo reaplicado
        (proporcional si se reaplicó menos de lo que se había desaplicado). Lo
        reaplicado de un pago se reparte entre sus reversos sin contarlo dos
        veces.
        """
        self.ensure_one()
        self = self.sudo()  # el mensual completo, sean cuales sean las compañías activas
        for model in ('sng.commission.payment.line', 'account.payment', 'account.move',
                      'account.move.line', 'account.partial.reconcile'):
            self.env[model].flush_model()
        self.env.cr.execute("""
            SELECT r.id AS reversal_id, inv.id AS invoice_id, SUM(pr.amount) AS amount
            FROM sng_commission_payment_line r
            JOIN account_payment p ON p.id = r.payment_id AND p.state IN ('in_process', 'paid')
            JOIN account_move_line pl ON pl.move_id = p.move_id
            JOIN account_account aa ON aa.id = pl.account_id AND aa.account_type = 'asset_receivable'
            JOIN account_partial_reconcile pr
              ON (pr.credit_move_id = pl.id OR pr.debit_move_id = pl.id)
             AND pr.create_date >= r.create_date
            JOIN account_move_line il
              ON il.id = CASE WHEN pr.credit_move_id = pl.id THEN pr.debit_move_id ELSE pr.credit_move_id END
            JOIN account_move inv
              ON inv.id = il.move_id AND inv.move_type = 'out_invoice' AND inv.state = 'posted'
            WHERE r.monthly_id = %(monthly)s AND r.line_type = 'reversal'
              AND NOT EXISTS (
                  SELECT 1 FROM sng_commission_payment_line c
                  WHERE c.payment_id = r.payment_id AND c.invoice_id = inv.id
                    AND c.line_type = 'commission' AND c.create_date >= r.create_date)
            GROUP BY r.id, inv.id
            ORDER BY r.id, inv.id
        """, {'monthly': self.id})
        reapplied = {}
        for reversal_id, invoice_id, amount in self.env.cr.fetchall():
            reapplied.setdefault(reversal_id, {})[invoice_id] = float(amount)

        Line = self.env['sng.commission.payment.line']
        Move = self.env['account.move']
        # Lo reaplicado de un pago a una factura se consume una sola vez aunque
        # el pago tenga varios reversos.
        remaining = {}

        def take(payment, invoice, available, needed):
            key = (payment.id, invoice.id)
            left = remaining.setdefault(key, available)
            taken = max(min(left, available, needed), 0.0)
            remaining[key] = left - taken
            return taken

        rows = []
        for reversal in Line.browse(list(reapplied)).sorted('id'):
            payment = reversal.payment_id
            amounts = reapplied[reversal.id]
            invoices = Move.browse(list(amounts))
            original = abs(reversal.payment_amount)
            needed = original
            notes = []
            owed = 0.0
            matched = 0.0
            same = reversal.invoice_id in invoices
            if same:
                taken = take(payment, reversal.invoice_id, amounts[reversal.invoice_id.id], needed)
                owed += taken
                matched += taken
                needed -= taken
                # "Generar comisiones" solo elimina el reverso si su mes sigue
                # abierto; el cierre no lo hace solo (el par ya tiene línea).
                if self.state == 'draft':
                    notes.append(_('Reaplicado a la misma factura: antes de cerrar el mes use '
                                   '"Generar comisiones" en el pago; eso elimina el reverso.'))
                elif self.state == 'closed':
                    notes.append(_('Reaplicado a la misma factura: con el mes cerrado "Generar comisiones" '
                                   'no lo recupera; hay que reabrir este mes y usarlo en el pago, o ajustar a mano.'))
                else:
                    notes.append(_('Reaplicado a la misma factura: el mes ya está facturado; '
                                   'hay que ajustar a mano en un mes abierto.'))
            others = invoices - reversal.invoice_id
            if others:
                # Al generar, la comisión es del vendedor de la factura nueva,
                # que puede no ser este vendedor.
                sellers = self.env['res.partner']
                seller_by_invoice = {}
                for invoice in others:
                    seller = False
                    if not invoice.sng_commission_exclude:
                        seller = payment._get_salesperson_for_commission(invoice)
                    seller_by_invoice[invoice] = seller
                    if seller:
                        sellers |= seller
                # Primero las facturas de este vendedor, para no restarle lo suyo.
                for invoice in others.sorted(lambda inv: seller_by_invoice[inv] != self.salesperson_id):
                    taken = take(payment, invoice, amounts[invoice.id], needed)
                    matched += taken
                    needed -= taken
                    if seller_by_invoice[invoice] == self.salesperson_id:
                        owed += taken
                if sellers:
                    notes.append(_(
                        'Reaplicado a otra factura: se recupera con "Generar comisiones" en el pago; '
                        'la comisión es de %(sellers)s.',
                        sellers=', '.join(sellers.mapped('name')),
                    ))
                else:
                    notes.append(_('Reaplicado a otra factura que no comisiona (sin vendedor o excluida).'))
            reversed_amount = -reversal.commission_adjustment
            proportion = min(owed / original, 1.0) if original else 0.0
            rows.append({
                'payment': payment.name,
                'receipt': reversal.sng_numero_recibo or payment.memo or '',
                'partner': reversal.partner_id.name,
                'original_period': reversal.original_monthly_id.period_label or '',
                'reversed_invoice': reversal.invoice_id.name,
                'new_invoices': ', '.join(invoices.mapped('name')),
                'same_invoice': same,
                'action': ' '.join(notes),
                'unapplied_amount': original,
                'reapplied_amount': matched,
                'reversed_amount': reversed_amount,
                # Solo la parte reaplicada que le toca a este vendedor.
                'amount': self.currency_id.round(reversed_amount * proportion),
            })
        return {
            'rows': rows,
            'reversed_amount': sum(row['reversed_amount'] for row in rows),
            'amount': sum(row['amount'] for row in rows),
        }
