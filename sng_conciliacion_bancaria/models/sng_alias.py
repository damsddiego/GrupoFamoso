# -*- coding: utf-8 -*-
"""Aprendizaje de conciliaciones: alias del banco → cliente.

Cada vez que una línea del extracto queda conciliada — por el flujo SNG, a
mano en el widget nativo o por el auto-reconcile — se aprende la asociación
entre el texto del banco (alias SINPE, nombre/cédula del TEF) y el cliente
de las contrapartidas. Al deshacer la conciliación se desaprende (el
contador baja). Lo aprendido se consume en la heurística y como candidato
extra para la IA, y también autocompleta el cliente en el widget nativo vía
_retrieve_partner.

La tabla es global entre compañías: el pagador es la misma persona pague a
la compañía que pague; el guard de compañía se aplica al usar el alias, no
al guardarlo.
"""
import logging

from odoo import _, api, fields, models

from .sng_matching import _sng_extraer_claves

_logger = logging.getLogger(__name__)

# Un alias asociado a esta cantidad (o más) de clientes distintos es texto
# genérico, no identifica a nadie: se desactiva completo.
SNG_ALIAS_MAX_PARTNERS = 3


class SngConciliacionAlias(models.Model):
    _name = 'sng.conciliacion.alias'
    _description = 'Alias aprendido banco → cliente'
    _order = 'contador desc, ultima_fecha desc'
    _rec_name = 'alias'

    alias = fields.Char(
        required=True, index=True, string='Alias',
        help='Texto normalizado extraído de la descripción del banco '
             '(sin prefijos TS/TF/SINPE ni el teléfono receptor).')
    tipo = fields.Selection([
        ('alias_sinpe', 'Alias SINPE'),
        ('nombre_tef', 'Nombre TEF'),
        ('cedula', 'Cédula en TEF'),
    ], required=True, default='alias_sinpe', string='Tipo')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True,
        ondelete='cascade', index=True)
    contador = fields.Integer(
        string='Aciertos', default=1,
        help='Conciliaciones confirmadas con este alias y este cliente. '
             'Con 2 o más la sugerencia sale con confianza alta; al '
             'deshacer una conciliación el contador baja.')
    ultima_fecha = fields.Date(string='Última conciliación')
    origen = fields.Selection([
        ('conciliacion', 'Conciliación'),
        ('bootstrap', 'Histórico'),
        ('manual', 'Manual'),
    ], default='manual', string='Origen')
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        help='Compañía donde se aprendió (solo informativo: el alias '
             'aplica a todas las compañías).')
    active = fields.Boolean(default=True, string='Activo')

    _sql_constraints = [
        ('alias_tipo_partner_uniq', 'unique(alias, tipo, partner_id)',
         'Ya existe ese alias para ese cliente.'),
    ]

    # ------------------------------------------------------------------
    # Aprender / desaprender (siempre con sudo: cualquier usuario que
    # concilie alimenta la tabla, tenga o no el grupo SNG)
    # ------------------------------------------------------------------
    @api.model
    def _sng_aprender(self, payment_ref, partner_id, company_id=None,
                      fecha=None, origen='conciliacion'):
        if not partner_id:
            return
        Alias = self.sudo().with_context(active_test=False)
        for tipo, clave in _sng_extraer_claves(payment_ref):
            fila = Alias.search([
                ('alias', '=', clave), ('tipo', '=', tipo),
                ('partner_id', '=', partner_id)], limit=1)
            if fila:
                fila.write({'contador': fila.contador + 1,
                            'ultima_fecha': fecha})
            else:
                Alias.create({
                    'alias': clave, 'tipo': tipo, 'partner_id': partner_id,
                    'contador': 1, 'ultima_fecha': fecha, 'origen': origen,
                    'company_id': company_id,
                })
            activas = Alias.search([
                ('alias', '=', clave), ('tipo', '=', tipo),
                ('active', '=', True)])
            if len(set(activas.mapped('partner_id').ids)) >= \
                    SNG_ALIAS_MAX_PARTNERS:
                activas.write({'active': False})
                _logger.warning(
                    'SNG aprendizaje: alias «%s» (%s) asociado a %s '
                    'clientes distintos; se desactiva por ambiguo.',
                    clave, tipo, len(set(activas.mapped('partner_id').ids)))

    @api.model
    def _sng_desaprender(self, payment_ref, partner_id):
        Alias = self.sudo().with_context(active_test=False)
        for tipo, clave in _sng_extraer_claves(payment_ref):
            fila = Alias.search([
                ('alias', '=', clave), ('tipo', '=', tipo),
                ('partner_id', '=', partner_id)], limit=1)
            if fila and fila.contador > 0:
                fila.contador -= 1

    @api.model
    def _sng_indice(self):
        """{(tipo, alias): (partner_id, contador)} de alias activos con
        exactamente un cliente (los ambiguos se omiten sin desactivar)."""
        self.flush_model()  # SQL crudo: ver lo escrito en esta transacción
        self.env.cr.execute("""
            SELECT tipo, alias, MIN(partner_id), MAX(contador)
            FROM sng_conciliacion_alias
            WHERE active AND contador >= 1
            GROUP BY tipo, alias
            HAVING COUNT(DISTINCT partner_id) = 1
        """)
        return {(t, a): (pid, cont)
                for t, a, pid, cont in self.env.cr.fetchall()}

    # ------------------------------------------------------------------
    # Bootstrap desde líneas ya conciliadas (histórico / restauraciones)
    # ------------------------------------------------------------------
    def accion_sng_bootstrap(self):
        self.env['account.bank.statement.line']._sng_verificar_grupo()
        # SQL directo (ver nota en sng_matching._sng_facturas_abiertas_sql)
        self.env.cr.execute("""
            SELECT l.payment_ref, l.partner_id, m.company_id, m.date
            FROM account_bank_statement_line l
            JOIN account_move m ON m.id = l.move_id
            WHERE l.is_reconciled AND l.amount > 0
              AND l.partner_id IS NOT NULL
        """)
        filas = self.env.cr.fetchall()
        aprendidas = 0
        for ref, partner_id, company_id, fecha in filas:
            if _sng_extraer_claves(ref):
                aprendidas += 1
            self._sng_aprender(ref, partner_id, company_id, fecha,
                               origen='bootstrap')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _(
                    '%(a)s de %(t)s línea(s) conciliada(s) dejaron alias '
                    'aprendido. Ojo: repetir este botón vuelve a sumar '
                    'aciertos sobre las mismas líneas.',
                    a=aprendidas, t=len(filas)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class BankRecWidget(models.Model):
    _inherit = 'bank.rec.widget'

    def _action_validate(self):
        res = super()._action_validate()
        # Aprender de TODA conciliación validada (flujo SNG, manual desde el
        # widget o auto-reconcile). Nunca puede tumbar la conciliación.
        try:
            st = self.st_line_id
            if st.amount > 0:
                _liq, _susp, otras = st._seek_for_lines()
                partners = otras.mapped('partner_id')
                if len(partners) == 1:
                    self.env['sng.conciliacion.alias']._sng_aprender(
                        st.payment_ref, partners.id, st.company_id.id,
                        st.date)
        except Exception:  # noqa: BLE001
            _logger.exception('SNG aprendizaje: no se pudo aprender de la '
                              'línea %s', self.st_line_id.id)
        return res


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def action_undo_reconciliation(self):
        # Capturar el cliente ANTES del super: el undo limpia line_ids.
        previos = []
        for st in self:
            try:
                if st.amount > 0:
                    _liq, _susp, otras = st._seek_for_lines()
                    partners = otras.mapped('partner_id')
                    if len(partners) == 1:
                        previos.append((st.payment_ref, partners.id))
            except Exception:  # noqa: BLE001
                _logger.exception('SNG aprendizaje: fallo leyendo línea %s '
                                  'antes del undo', st.id)
        res = super().action_undo_reconciliation()
        for ref, partner_id in previos:
            try:
                self.env['sng.conciliacion.alias']._sng_desaprender(
                    ref, partner_id)
            except Exception:  # noqa: BLE001
                _logger.exception('SNG aprendizaje: fallo al desaprender')
        return res

    def _retrieve_partner(self):
        partner = super()._retrieve_partner()
        if partner or self.amount <= 0:
            return partner
        # Último recurso: alias aprendido (autocompleta el cliente en el
        # widget nativo y en el auto-reconcile).
        try:
            idx = self.env['sng.conciliacion.alias']._sng_indice()
            for clave in _sng_extraer_claves(self.payment_ref):
                info = idx.get(clave)
                if not info:
                    continue
                cand = self.env['res.partner'].sudo().browse(info[0])
                # partners atados a otra compañía no caben en la línea
                # (_check_company); mismo guard que _sng_escribir
                if cand.exists() and (not cand.company_id
                                      or cand.company_id == self.company_id):
                    return self.env['res.partner'].browse(cand.id)
                break
        except Exception:  # noqa: BLE001
            _logger.exception('SNG aprendizaje: fallo en _retrieve_partner '
                              'de la línea %s', self.id)
        return partner
