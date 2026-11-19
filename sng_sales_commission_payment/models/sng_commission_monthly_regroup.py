# -*- coding: utf-8 -*-

import logging
from collections import defaultdict

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SngCommissionMonthlyRegroup(models.Model):
    """Reagrupar meses abiertos.

    Regla: toda línea de un mensual en borrador debe estar en el mensual del
    cuadro que rige para su compañía (la del pago) en ese mes. Deja de
    cumplirse cuando se crea o cambia un cuadro con meses ya abiertos: por
    ejemplo, al juntar varias compañías en un cuadro de grupo, los borradores
    que cada vendedor tenía por compañía pasan a ser uno solo.
    """
    _inherit = 'sng.commission.monthly'

    @api.model
    def _sng_regroup_open(self, dry_run=False, monthlies=None):
        """Mueve cada línea de los mensuales en borrador (todos, o solo los de
        ``monthlies``) al mensual de su cuadro vigente, creándolo si falta;
        borra los borradores que quedan vacíos en un cuadro que ya no rige y
        recalcula. Con ``dry_run`` solo cuenta.

        Un vendedor y mes se omite completo si en el cuadro destino tiene un
        mensual que ya no está en borrador (suyo o de un cuadro anterior de
        esas compañías): quedaría partido entre un mes cerrado y uno abierto.

        Devuelve ``{'moved_lines', 'created_monthlies', 'removed_monthlies',
        'skipped': [{'salesperson', 'period', 'reason'}]}``.
        """
        Monthly = self.sudo()
        Scheme = self.env['sng.commission.scheme'].sudo()
        Line = self.env['sng.commission.payment.line'].sudo()
        if monthlies is None:
            drafts = Monthly.search([('state', '=', 'draft')])
        else:
            drafts = monthlies.sudo().filtered(lambda m: m.state == 'draft')

        ruling = {}

        def scheme_for(company, period):
            if (company, period) not in ruling:
                ruling[(company, period)] = Scheme._get_for_company(company, period)
            return ruling[(company, period)]

        # Líneas fuera de su cuadro, por destino (vendedor, mes, cuadro vigente).
        moves = defaultdict(lambda: Line)
        for monthly in drafts:
            for line in monthly.line_ids:
                target = scheme_for(line.company_id, monthly.period)
                if target and target != monthly.scheme_id:
                    moves[(monthly.salesperson_id, monthly.period, target)] |= line

        result = {'moved_lines': 0, 'created_monthlies': 0, 'removed_monthlies': 0, 'skipped': []}
        planned = []
        for (salesperson, period, target), lines in moves.items():
            blocking = Monthly.search([
                ('salesperson_id', '=', salesperson.id),
                ('period', '=', period),
                ('state', '!=', 'draft'),
                ('scheme_id.company_ids', 'in', target.company_ids.ids),
            ], limit=1)
            if blocking:
                result['skipped'].append({
                    'salesperson': salesperson,
                    'period': period,
                    'reason': _(
                        "%(monthly)s (cuadro %(scheme)s) ya no está pendiente.",
                        monthly=blocking.name, scheme=blocking.scheme_id.name),
                })
                continue
            destination = Monthly.search([
                ('salesperson_id', '=', salesperson.id),
                ('period', '=', period),
                ('scheme_id', '=', target.id),
            ], limit=1)
            planned.append((salesperson, period, target, destination, lines))
            result['moved_lines'] += len(lines)
            result['created_monthlies'] += 0 if destination else 1

        moved = Line.union(*(lines for *_key, lines in planned))
        # Borradores que quedan sin líneas en un cuadro que ya no rige para
        # ninguna de sus compañías ese mes.
        emptied = drafts.filtered(
            lambda m: not (m.line_ids - moved) and all(
                scheme_for(company, m.period) != m.scheme_id for company in m.scheme_id.company_ids))
        result['removed_monthlies'] = len(emptied)
        if dry_run or not (planned or emptied):
            return result

        sources = moved.mapped('monthly_id')
        destinations = Monthly
        for salesperson, period, target, destination, lines in planned:
            if not destination:
                destination = Monthly.create({
                    'salesperson_id': salesperson.id,
                    'scheme_id': target.id,
                    'company_id': target.company_ids.id if len(target.company_ids) == 1 else False,
                    'period': period,
                })
            destinations |= destination
        affected = sources | destinations
        before = self._sng_regroup_totals(affected)
        for (salesperson, period, target, _destination, lines) in planned:
            destination = destinations.filtered(
                lambda m: m.salesperson_id == salesperson and m.period == period and m.scheme_id == target)
            lines.write({'monthly_id': destination.id})
        emptied.unlink()
        # Después de borrar los vacíos: si alguno hubiera tenido líneas, el
        # borrado en cascada se las llevaría y aquí se nota.
        if self._sng_regroup_totals(affected) != before:
            raise UserError(_(
                "Al reagrupar cambió la cantidad de líneas o la suma de bases; no se guardó nada."))
        (affected - emptied)._recompute_commission()
        _logger.info(
            "Comisiones reagrupadas: %(moved_lines)s líneas movidas, %(created_monthlies)s mensuales "
            "creados, %(removed_monthlies)s eliminados.", result)
        return result

    @api.model
    def _sng_regroup_totals(self, monthlies):
        """(líneas, base, ajustes) de un conjunto de mensuales, directo de la base."""
        if not monthlies:
            return (0, 0.0, 0.0)
        self.env['sng.commission.payment.line'].flush_model()
        self.env.cr.execute("""
            SELECT count(*), COALESCE(sum(round(commission_base::numeric, 2)), 0),
                   COALESCE(sum(round(commission_adjustment::numeric, 2)), 0)
              FROM sng_commission_payment_line
             WHERE monthly_id IN %s""", (tuple(monthlies.ids),))
        return self.env.cr.fetchone()

    def _sng_regroup_pending_for_close(self):
        """Líneas que habría que reagrupar antes de cerrar estos mensuales:
        las de cualquier borrador del mismo mes en sus compañías."""
        companies = self.sudo().mapped('scheme_id.company_ids')
        scope = self.sudo().search([
            ('state', '=', 'draft'),
            ('period', 'in', list(set(self.mapped('period')))),
            ('scheme_id.company_ids', 'in', companies.ids),
        ])
        return self._sng_regroup_open(dry_run=True, monthlies=scope)['moved_lines']
