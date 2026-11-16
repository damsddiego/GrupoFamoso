# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
from datetime import timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from . import cruces

_logger = logging.getLogger(__name__)

CR_TZ = pytz.timezone('America/Costa_Rica')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
MESES_CONSULTABLES = 7  # mes actual + 6 anteriores
DIAS_REEMPLAZO = 14
GRUPOS_CONSULTA = (
    'sng_comisiones_vendedor.group_comisiones_app',      # usuario RPC de la app
    'sales_commission_omax.group_sales_commission_user',  # oficina de comisiones
)


class SngComisionEstado(models.AbstractModel):
    """Estado de comisiones de un vendedor: lo consulta la app («Mis
    comisiones») y el asistente de oficina. Solo lectura, salvo el cron
    opcional que genera las líneas que faltan."""
    _name = 'sng.comision.estado'
    _description = 'Estado de comisiones del vendedor'

    # ------------------------------------------------------------------ API
    @api.model
    def obtener_estado(self, vendedor_id, periodo=None):
        """Cruces del vendedor (``res.partner`` con ``is_salesperson``, o el
        id que manda la app) en el mes de ``periodo`` (AAAA-MM-DD; por
        defecto el mes actual en CR)."""
        if not any(self.env.user.has_group(g) for g in GRUPOS_CONSULTA):
            raise AccessError(_(
                'Su usuario no tiene permiso para consultar comisiones '
                '(grupo «Comisiones: consulta desde la app»).'))
        env = self.sudo().with_context(
            allowed_company_ids=self.env['res.company'].sudo().search([]).ids).env
        vendedor = self._resolver_vendedor(env, vendedor_id)
        vendedores = self._contactos_del_vendedor(env, vendedor)

        hoy = self._hoy_cr()
        periodo = fields.Date.to_date(periodo).replace(day=1) if periodo else hoy.replace(day=1)
        Monthly = env['sng.commission.monthly']
        desde, hasta = Monthly._sng_period_bounds(periodo)

        mensuales = Monthly.search([('salesperson_id', 'in', vendedores.ids), ('period', '=', periodo)])
        lineas = env['sng.commission.payment.line'].search([('monthly_id', 'in', mensuales.ids)])
        Payment = env['account.payment']
        reportados = Payment.search([
            ('sng_from_app', '=', True),
            ('sng_origen', '!=', 'escritorio'),
            ('sng_vendedor_id', 'in', vendedores.ids),
            ('date', '>=', desde), ('date', '<=', hasta),
        ])
        pendientes = self._pendientes(env, vendedores, reportados, desde, hasta)
        anulados = reportados.filtered(lambda p: p.state in cruces.ANULADOS)
        duplicados, reemplazos = {}, {}
        for pago in anulados:
            original = self._original_duplicado(env, pago)
            if original:
                duplicados[pago.id] = original
                continue
            reemplazo = self._reemplazo(env, pago)
            if reemplazo:
                reemplazos[pago.id] = reemplazo
        quien_anulo = self._quien_anulo(env, anulados)

        todos = reportados | lineas.mapped('payment_id') \
            | Payment.browse([f['payment_id'] for f in pendientes]) \
            | Payment.union(*reemplazos.values(), *duplicados.values())
        duenos = self._duenos_comision(env, todos)
        pagos = {p.id: self._pago_dict(p, duenos.get(p.id, {}), quien_anulo.get(p.id)) for p in todos}

        return cruces.armar_estado(
            vendedores.ids, vendedor.name, str(periodo),
            mensuales=[{
                'compania_id': m.company_id.id, 'compania': m.company_id.name,
                'salesperson_id': m.salesperson_id.id, 'vendedor': m.salesperson_id.name,
                'estado': m.state, 'base': m.base_amount, 'porcentaje': m.percentage,
                'comision': m.commission_amount, 'ajustes': m.adjustment_amount,
            } for m in mensuales],
            lineas=[{
                'payment_id': l.payment_id.id, 'compania_id': l.monthly_id.company_id.id,
                'line_type': l.line_type, 'base': l.commission_base,
                'ajuste': l.commission_adjustment, 'motivo_reverso': l.reversal_reason or '',
                'periodo_original': str(l.original_monthly_id.period or ''),
            } for l in lineas],
            pagos=pagos,
            reportados_ids=reportados.ids,
            tramos=self._tramos(env),
            pendientes=pendientes,
            reemplazos={k: pagos[v.id] for k, v in reemplazos.items()},
            duplicados={k: pagos[v.id] for k, v in duplicados.items()},
            periodos=self._periodos(env, vendedores, hoy),
            generado=fields.Datetime.now().replace(tzinfo=pytz.utc).astimezone(CR_TZ).isoformat(),
        )

    # ------------------------------------------------------------ helpers
    @api.model
    def _hoy_cr(self):
        return fields.Datetime.now().replace(tzinfo=pytz.utc).astimezone(CR_TZ).date()

    @api.model
    def _resolver_vendedor(self, env, vendedor_id):
        """El id que manda la app puede no existir (contacto fusionado o
        borrado): se traduce con las equivalencias de sng_ruteros_pagos."""
        Partner = env['res.partner'].with_context(active_test=False)
        resuelto, _aviso = Partner._sng_resolver_vendedor_app(int(vendedor_id))
        vendedor = Partner.browse(resuelto).exists() if resuelto else Partner
        if not vendedor or not vendedor.is_salesperson:
            raise UserError(_(
                'El contacto %s no es un vendedor en Odoo (o no tiene equivalencia '
                'configurada). Avise a la oficina.') % vendedor_id)
        return vendedor

    @api.model
    def _contactos_del_vendedor(self, env, vendedor):
        """El vendedor y sus contactos duplicados (vendedores con el mismo
        nombre normalizado, como en el análisis de comisiones)."""
        nombre = cruces.normalizar_nombre(vendedor.name)
        vendedores = env['res.partner'].with_context(active_test=False).search(
            [('is_salesperson', '=', True)])
        return vendedor | vendedores.filtered(lambda v: cruces.normalizar_nombre(v.name) == nombre)

    @api.model
    def _periodos(self, env, vendedores, hoy):
        actual = hoy.replace(day=1)
        meses = [actual - relativedelta(months=i) for i in range(MESES_CONSULTABLES)]
        mensuales = env['sng.commission.monthly'].search([
            ('salesperson_id', 'in', vendedores.ids), ('period', 'in', meses)])
        resultado = []
        for mes in meses:
            del_mes = mensuales.filtered(lambda m: m.period == mes)
            resultado.append({
                'periodo': str(mes),
                'etiqueta': '%s %s' % (MESES[mes.month - 1], mes.year),
                'estados': [{
                    'compania': m.company_id.name, 'estado': m.state,
                    'estado_texto': cruces.ESTADOS_MES.get(m.state, m.state),
                } for m in del_mes],
            })
        return resultado

    @api.model
    def _tramos(self, env):
        tramos = {}
        for t in env['sng.commission.tier'].search([('active', '=', True)]):
            tramos.setdefault(t.company_id.id, []).append((t.min_amount, t.percentage))
        return tramos

    @api.model
    def _pendientes(self, env, vendedores, reportados, desde, hasta):
        """Pares (pago, factura) confirmados sin línea de comisión que son del
        vendedor (en el mes) o de un pago que él reportó (en cualquier mes,
        solo para explicar el motivo). Solo lectura.

        Replica las reglas de ``_sng_find_uncommissioned`` del addon de
        comisiones, pero filtrando por el vendedor dentro del SQL y con el
        filtro de fechas partido para que use los índices de
        ``sng_confirmation_date`` y ``account_move.date``."""
        env['account.payment'].flush_model()
        env['account.move'].flush_model(['state', 'move_type', 'salesperson_id', 'assigned_salesperson_id',
                                         'sng_commission_exclude', 'date'])
        env['account.partial.reconcile'].flush_model()
        env['sng.commission.payment.line'].flush_model()
        env['res.partner'].flush_model(['is_salesperson', 'assigned_salesperson_id'])
        params = {
            'companies': env['res.company'].search([]).ids,
            'desde': desde,
            'hasta': hasta,
            'vendedores': vendedores.ids,
            'reportados': reportados.filtered(lambda p: p.state in cruces.ACTIVOS).ids or [0],
        }
        env.cr.execute("""
            WITH en_mes AS (
                SELECT p.id AS pid, p.move_id, p.partner_id, p.company_id
                  FROM account_payment p
                 WHERE p.payment_type = 'inbound'
                   AND p.state IN ('in_process', 'paid')
                   AND p.company_id = ANY(%(companies)s)
                   AND p.sng_confirmation_date BETWEEN %(desde)s AND %(hasta)s
                UNION ALL
                SELECT p.id, p.move_id, p.partner_id, p.company_id
                  FROM account_move m
                  JOIN account_payment p ON p.move_id = m.id
                 WHERE m.date BETWEEN %(desde)s AND %(hasta)s
                   AND p.sng_confirmation_date IS NULL
                   AND p.payment_type = 'inbound'
                   AND p.state IN ('in_process', 'paid')
                   AND p.company_id = ANY(%(companies)s)
            ),
            pays AS (
                SELECT pid, move_id, partner_id, company_id, TRUE AS en_mes FROM en_mes
                UNION ALL
                SELECT p.id, p.move_id, p.partner_id, p.company_id, FALSE
                  FROM account_payment p
                 WHERE p.id = ANY(%(reportados)s)
                   AND p.id NOT IN (SELECT pid FROM en_mes)
            ),
            pairs AS (
                SELECT DISTINCT pays.pid, pays.partner_id, pays.company_id, pays.en_mes,
                       inv.id AS inv_id, inv.salesperson_id, inv.assigned_salesperson_id
                  FROM pays
                  JOIN account_move_line pl ON pl.move_id = pays.move_id
                  JOIN account_account aa ON aa.id = pl.account_id AND aa.account_type = 'asset_receivable'
                  JOIN account_partial_reconcile pr ON pr.credit_move_id = pl.id OR pr.debit_move_id = pl.id
                  JOIN account_move_line il
                    ON il.id = CASE WHEN pr.credit_move_id = pl.id THEN pr.debit_move_id ELSE pr.credit_move_id END
                  JOIN account_move inv
                    ON inv.id = il.move_id AND inv.move_type IN ('out_invoice', 'out_refund') AND inv.state = 'posted'
                   AND NOT COALESCE(inv.sng_commission_exclude, FALSE)
                  LEFT JOIN res_partner cust ON cust.id = pays.partner_id
                 WHERE pays.pid = ANY(%(reportados)s)
                    OR inv.salesperson_id = ANY(%(vendedores)s)
                    OR inv.assigned_salesperson_id = ANY(%(vendedores)s)
                    OR (cust.assigned_salesperson_id->>pays.company_id::text)::int = ANY(%(vendedores)s)
            ),
            resueltos AS (
                SELECT pr.pid, pr.inv_id, pr.company_id, pr.en_mes,
                       COALESCE(
                         (SELECT sp.id FROM res_partner sp WHERE sp.id = pr.salesperson_id AND sp.is_salesperson),
                         (SELECT sp.id FROM res_partner sp WHERE sp.id = pr.assigned_salesperson_id AND sp.is_salesperson),
                         (SELECT sp.id FROM res_partner sp
                            JOIN res_partner cust ON (cust.assigned_salesperson_id->>pr.company_id::text)::int = sp.id
                           WHERE cust.id = pr.partner_id AND sp.is_salesperson)
                       ) AS salesperson_id
                  FROM pairs pr
                 WHERE NOT EXISTS (
                     SELECT 1 FROM sng_commission_payment_line l
                      WHERE l.payment_id = pr.pid AND l.invoice_id = pr.inv_id AND l.line_type = 'commission')
            )
            SELECT pid, inv_id, company_id, en_mes, salesperson_id
              FROM resueltos
             WHERE pid = ANY(%(reportados)s) OR salesperson_id = ANY(%(vendedores)s)
             ORDER BY pid, inv_id
        """, params)
        filas = env.cr.fetchall()
        if not filas:
            return []

        mios = set(vendedores.ids)
        nombres = {p.id: p.name for p in env['res.partner'].browse({f[4] for f in filas if f[4]})}
        companias = {c.id: c.name for c in env['res.company'].browse({f[2] for f in filas})}
        # Base como la calcula _generate_commission_lines: una lectura por pago.
        aplicado = {}
        for pid in {f[0] for f in filas if f[4] in mios and f[3]}:
            for factura, _partial, monto in env['account.payment'].browse(pid)._get_reconciled_invoice_partials():
                if factura.amount_total:
                    aplicado[(pid, factura.id)] = monto * factura.amount_untaxed / factura.amount_total
        return [{
            'payment_id': pid, 'compania_id': cid, 'compania': companias.get(cid, ''),
            'salesperson_id': sp or None, 'vendedor': nombres.get(sp, ''),
            'base': aplicado.get((pid, inv_id), 0.0), 'en_mes': bool(en_mes),
        } for pid, inv_id, cid, en_mes, sp in filas]

    @api.model
    def _numeros(self, env, pago):
        return set(pago.reconciled_invoice_ids.mapped('name')) | \
            env['account.payment']._sng_numeros_factura_desde_texto(pago.sng_observaciones or '')

    @api.model
    def _original_duplicado(self, env, pago):
        """Pago activo del que este anulado era duplicado (marcado por la
        detección de duplicados de sng_ruteros_pagos, en cualquier sentido)."""
        relacionados = pago.sng_dup_pago_ids | env['account.payment'].search(
            [('sng_dup_pago_ids', 'in', pago.id)])
        activos = relacionados.filtered(lambda p: p.id != pago.id and p.state in cruces.ACTIVOS)
        return activos.sorted('create_date')[:1]

    @api.model
    def _reemplazo(self, env, pago):
        """Pago activo, posterior, del mismo cliente comercial y compañía, con
        el mismo monto o la misma factura (deducción, no hay liga real)."""
        if not pago.partner_id or not pago.date:
            return False
        candidatos = env['account.payment'].search([
            ('id', '!=', pago.id),
            ('partner_id', 'child_of', pago.partner_id.commercial_partner_id.id),
            ('company_id', '=', pago.company_id.id),
            ('payment_type', '=', 'inbound'),
            ('state', 'in', cruces.ACTIVOS),
            ('create_date', '>', pago.create_date),
            ('date', '<=', pago.date + timedelta(days=DIAS_REEMPLAZO)),
        ], order='create_date, id')
        numeros = self._numeros(env, pago)
        for candidato in candidatos:
            if abs(candidato.amount - pago.amount) <= 0.01:
                return candidato
            if numeros and numeros & self._numeros(env, candidato):
                return candidato
        return False

    @api.model
    def _quien_anulo(self, env, pagos):
        """{pago: (usuario, fecha)} del último cambio de estado registrado."""
        if not pagos:
            return {}
        campo = env['ir.model.fields']._get('account.payment', 'state')
        resultado = {}
        cambios = env['mail.tracking.value'].search([
            ('field_id', '=', campo.id),
            ('mail_message_id.model', '=', 'account.payment'),
            ('mail_message_id.res_id', 'in', pagos.ids),
        ], order='id desc')
        for cambio in cambios:
            resultado.setdefault(cambio.mail_message_id.res_id, (
                cambio.create_uid.name, cambio.create_date))
        for pago in pagos:
            resultado.setdefault(pago.id, (pago.write_uid.name, pago.write_date))
        return resultado

    @api.model
    def _duenos_comision(self, env, pagos):
        """{pago: {vendedor_id: nombre}} de sus líneas de comisión (cualquier mes)."""
        duenos = defaultdict(dict)
        for linea in env['sng.commission.payment.line'].search([
                ('payment_id', 'in', pagos.ids), ('line_type', '=', 'commission')]):
            duenos[linea.payment_id.id][linea.salesperson_id.id] = linea.salesperson_id.name
        return duenos

    @api.model
    def _pago_dict(self, pago, comision_de, anulado):
        facturas = pago.reconciled_invoice_ids.mapped('name')
        if not facturas:
            facturas = sorted(self.env['account.payment']._sng_numeros_factura_desde_texto(
                pago.sng_observaciones or ''))
        anulado_por, anulado_el = anulado or ('', False)
        if anulado_el:
            anulado_el = anulado_el.replace(tzinfo=pytz.utc).astimezone(CR_TZ).isoformat()
        return {
            'id': pago.id,
            'nombre': pago.name or '',
            'recibo': pago.sng_numero_recibo or '',
            'fecha': str(pago.date or ''),
            'fecha_confirmacion': str(pago.sng_confirmation_date or ''),
            'cliente': pago.partner_id.display_name or '',
            'compania_id': pago.company_id.id,
            'compania': pago.company_id.name,
            'monto': pago.amount,
            'estado': pago.state,
            'verificado': pago.sng_verificado,
            'de_app': pago.sng_from_app and pago.sng_origen != 'escritorio',
            'vendedor_id': pago.sng_vendedor_id.id or False,
            'vendedor': pago.sng_vendedor_id.name or '',
            'creado_por': pago.create_uid.name or '',
            'observaciones': pago.sng_observaciones or '',
            'facturas': facturas,
            'dup_estado': pago.sng_dup_estado or '',
            'monto_atipico': pago.sng_monto_atipico,
            'ia_estado': pago.sng_ia_estado or '',
            'conciliado': bool(pago.reconciled_invoice_ids),
            'comision_de': dict(comision_de),
            'anulado_por': anulado_por or '',
            'anulado_el': anulado_el or '',
        }

    # ----------------------------------------------------------------- cron
    @api.model
    def _cron_generar_pendientes(self):
        """Genera las líneas de comisión de los cobros confirmados del mes
        actual y del anterior que aún no las tienen (los pagos de la app no
        pasan por ``action_post``). Es lo mismo que hace el cierre de mes.

        Apagado al instalar: antes de encenderlo hay que corregir en
        sng_sales_commission_payment que ``_generate_commission_lines``
        reescribe ``salesperson_id`` de líneas existentes."""
        Monthly = self.env['sng.commission.monthly'].sudo()
        actual = self._hoy_cr().replace(day=1)
        for company in self.env['res.company'].sudo().search([]):
            for periodo in (actual - relativedelta(months=1), actual):
                desde, hasta = Monthly._sng_period_bounds(periodo)
                Monthly.with_company(company)._sng_generate_pending(company, desde, hasta)
