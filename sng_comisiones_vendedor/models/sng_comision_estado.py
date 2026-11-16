# -*- coding: utf-8 -*-
import logging
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


class SngComisionEstado(models.AbstractModel):
    """Estado de comisiones de un vendedor: lo consulta la app («Mis
    comisiones») y el asistente de oficina. Solo lectura, salvo el cron
    opcional que genera las líneas que faltan."""
    _name = 'sng.comision.estado'
    _description = 'Estado de comisiones del vendedor'

    # ------------------------------------------------------------------ API
    @api.model
    def obtener_estado(self, vendedor_id, periodo=None):
        """Cruces del vendedor (``res.partner`` con ``is_salesperson``) en el
        mes de ``periodo`` (AAAA-MM-DD; por defecto el mes actual en CR)."""
        if not self.env.user.has_group('base.group_user'):
            raise AccessError(_('Solo usuarios internos pueden consultar comisiones.'))
        env = self.sudo().with_context(
            allowed_company_ids=self.env['res.company'].sudo().search([]).ids).env
        vendedor = env['res.partner'].browse(int(vendedor_id)).exists()
        if not vendedor or not vendedor.is_salesperson:
            raise UserError(_('El contacto %s no es un vendedor.') % vendedor_id)

        hoy = self._hoy_cr()
        periodo = fields.Date.to_date(periodo).replace(day=1) if periodo else hoy.replace(day=1)
        Monthly = env['sng.commission.monthly']
        desde, hasta = Monthly._sng_period_bounds(periodo)

        mensuales = Monthly.search([('salesperson_id', '=', vendedor.id), ('period', '=', periodo)])
        lineas = env['sng.commission.payment.line'].search([('monthly_id', 'in', mensuales.ids)])
        Payment = env['account.payment']
        reportados = Payment.search([
            ('sng_from_app', '=', True),
            ('sng_vendedor_id', '=', vendedor.id),
            ('date', '>=', desde), ('date', '<=', hasta),
        ])
        pendientes = self._pendientes(env, vendedor, reportados, desde, hasta)
        anulados = reportados.filtered(lambda p: p.state in cruces.ANULADOS)
        reemplazos = {p.id: self._reemplazo(env, p) for p in anulados}
        reemplazos = {k: v for k, v in reemplazos.items() if v}
        quien_anulo = self._quien_anulo(env, anulados)

        todos = reportados | lineas.mapped('payment_id') | Payment.browse(
            [f['payment_id'] for f in pendientes]) | Payment.union(*reemplazos.values())
        duenos = self._duenos_comision(env, todos)
        pagos = {p.id: self._pago_dict(p, duenos.get(p.id, {}), quien_anulo.get(p.id)) for p in todos}

        return cruces.armar_estado(
            vendedor.id, vendedor.name, str(periodo),
            mensuales=[{
                'compania_id': m.company_id.id, 'compania': m.company_id.name, 'estado': m.state,
                'base': m.base_amount, 'porcentaje': m.percentage,
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
            periodos=self._periodos(env, vendedor, hoy),
            generado=fields.Datetime.now().replace(tzinfo=pytz.utc).astimezone(CR_TZ).isoformat(),
        )

    # ------------------------------------------------------------ helpers
    @api.model
    def _hoy_cr(self):
        return fields.Datetime.now().replace(tzinfo=pytz.utc).astimezone(CR_TZ).date()

    @api.model
    def _periodos(self, env, vendedor, hoy):
        actual = hoy.replace(day=1)
        meses = [actual - relativedelta(months=i) for i in range(MESES_CONSULTABLES)]
        mensuales = env['sng.commission.monthly'].search([
            ('salesperson_id', '=', vendedor.id), ('period', 'in', meses)])
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
    def _pendientes(self, env, vendedor, reportados, desde, hasta):
        """Pares (pago, factura) cobrados en el mes sin línea de comisión que
        son del vendedor o de un pago que él reportó. Solo lectura."""
        Monthly = env['sng.commission.monthly']
        Payment = env['account.payment']
        filas = []
        mios = set(reportados.ids)
        for company in env['res.company'].search([]):
            for fila in Monthly._sng_find_uncommissioned(company, desde, hasta):
                if fila['salesperson_id'] != vendedor.id and fila['payment_id'] not in mios:
                    continue
                base = 0.0
                if fila['salesperson_id'] == vendedor.id:
                    pago = Payment.browse(fila['payment_id'])
                    for factura, _partial, monto in pago._get_reconciled_invoice_partials():
                        if factura.id == fila['invoice_id'] and factura.amount_total:
                            base = monto * factura.amount_untaxed / factura.amount_total
                filas.append({
                    'payment_id': fila['payment_id'], 'compania_id': company.id,
                    'compania': company.name, 'salesperson_id': fila['salesperson_id'],
                    'base': base,
                })
        return filas

    @api.model
    def _numeros(self, env, pago):
        return set(pago.reconciled_invoice_ids.mapped('name')) | \
            env['account.payment']._sng_numeros_factura_desde_texto(pago.sng_observaciones or '')

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
            ('state', 'not in', cruces.ANULADOS),
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
        duenos = {}
        for linea in env['sng.commission.payment.line'].search([
                ('payment_id', 'in', pagos.ids), ('line_type', '=', 'commission')]):
            duenos.setdefault(linea.payment_id.id, {})[linea.salesperson_id.id] = linea.salesperson_id.name
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
            'comision_de': comision_de,
            'anulado_por': anulado_por or '',
            'anulado_el': anulado_el or '',
        }

    # ----------------------------------------------------------------- cron
    @api.model
    def _cron_generar_pendientes(self):
        """Genera las líneas de comisión de los cobros confirmados del mes
        actual y del anterior que aún no las tienen (los pagos de la app no
        pasan por ``action_post``). Es lo mismo que hace el cierre de mes."""
        Monthly = self.env['sng.commission.monthly'].sudo()
        actual = self._hoy_cr().replace(day=1)
        for company in self.env['res.company'].sudo().search([]):
            for periodo in (actual - relativedelta(months=1), actual):
                desde, hasta = Monthly._sng_period_bounds(periodo)
                Monthly.with_company(company)._sng_generate_pending(company, desde, hasta)
