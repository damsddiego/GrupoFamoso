# -*- coding: utf-8 -*-
import calendar
import logging
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models

from .sng_ruteros_visita import EFECTIVIDAD_VISITA, RESULTADOS_COMERCIALES
from .sng_sales_route import DIAS_FRECUENCIA, FRECUENCIAS, TIPOS_ATENCION
from .sng_televentas_seguimiento import (
    CANALES, EFECTIVIDAD_TELEVENTAS, RESULTADOS_TELEVENTAS)

_logger = logging.getLogger(__name__)

ESTADOS_ATENCION = [
    ('sin_gestion', 'Sin gestión'),
    ('visitado', 'Visitado'),
    ('solo_televentas', 'Solo televentas'),
    ('pendiente_visita', 'Pendiente visita'),
]

RESPONSABLES = [
    ('ambos', 'Agente / Televentas'),
    ('agente', 'Agente'),
    ('televentas', 'Televentas'),
    ('sin_accion', 'Sin acción vencida'),
]

ALERTAS = [
    ('sin_atencion', 'CLIENTE SIN ATENCIÓN'),
    ('mas_90_dias', 'Más de N días sin facturar'),
    ('seguimiento_vencido', 'Seguimiento vencido'),
    ('ok', 'OK'),
]
ALERTA_ORDEN = {'sin_atencion': 0, 'mas_90_dias': 1,
                'seguimiento_vencido': 2, 'ok': 3}


class SngControlVisitasLinea(models.Model):
    """Una fila por cliente y mes: la "Matriz Comercial" de gerencia.

    Los campos calculados se escriben en la generación (no son compute)
    para que una sola pasada deje la fila consistente con la fecha de corte.
    """

    _name = 'sng.control.visitas.linea'
    _description = 'Matriz de control de visitas'
    _order = 'alerta_orden, sales_route_id, commercial_name, id'
    _rec_name = 'commercial_name'

    # ---- período
    periodo = fields.Char(string='Período', required=True, index=True)
    fecha_desde = fields.Date(string='Desde', required=True)
    fecha_hasta = fields.Date(string='Hasta', required=True)
    fecha_corte = fields.Date(string='Fecha de corte', required=True)
    fecha_generacion = fields.Datetime(string='Generado', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda')

    # ---- maestros
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, index=True,
        ondelete='cascade')
    unique_id = fields.Char(string='ID Cliente', readonly=True)
    name = fields.Char(string='Razón social', readonly=True)
    commercial_name = fields.Char(string='Nombre comercial', readonly=True)
    route_code = fields.Char(string='Código ruta', readonly=True)
    sales_route_id = fields.Many2one(
        'sng.sales.route', string='Ruta', readonly=True, index=True)
    vendedor_id = fields.Many2one(
        'res.partner', string='Agente asignado', readonly=True, index=True)
    phone = fields.Char(string='Teléfono', readonly=True)
    payment_term_name = fields.Char(string='Términos de pago', readonly=True)
    pricelist_name = fields.Char(string='Lista de precio', readonly=True)
    last_invoice_date = fields.Date(string='Fecha última factura', readonly=True)
    address = fields.Char(string='Dirección', readonly=True)
    tipo_atencion = fields.Selection(
        TIPOS_ATENCION, string='Tipo de atención', readonly=True)
    frecuencia_visita = fields.Selection(
        FRECUENCIAS, string='Frecuencia', readonly=True)

    # ---- bloque agente
    visita_id = fields.Many2one(
        'sng.ruteros.visita', string='Visita', readonly=True)
    fecha_visita_programada = fields.Date(
        string='Fecha visita programada', readonly=True)
    fecha_visita_realizada = fields.Date(
        string='Fecha visita realizada', readonly=True)
    resultado_visita = fields.Selection(
        RESULTADOS_COMERCIALES, string='Resultado visita', readonly=True)
    monto_venta_visita = fields.Monetary(
        string='Monto venta visita', currency_field='currency_id',
        readonly=True)
    motivo_sin_venta_id = fields.Many2one(
        'sng.visita.catalogo', string='Motivo sin venta', readonly=True)
    proxima_accion_agente_id = fields.Many2one(
        'sng.visita.catalogo', string='Próxima acción agente', readonly=True)
    fecha_proxima_accion_agente = fields.Date(
        string='Fecha próxima acción agente', readonly=True)
    comentario_agente = fields.Text(string='Comentario agente', readonly=True)
    requiere_seguimiento_televentas = fields.Boolean(
        string='Requiere televentas', readonly=True)

    # ---- bloque televentas
    seguimiento_id = fields.Many2one(
        'sng.televentas.seguimiento', string='Seguimiento', readonly=True)
    seguimiento_pendiente_id = fields.Many2one(
        'sng.televentas.seguimiento', string='Pendiente abierto',
        readonly=True)
    fecha_seguimiento = fields.Date(
        string='Fecha seguimiento televentas', readonly=True)
    canal = fields.Selection(CANALES, string='Canal', readonly=True)
    resultado_televentas = fields.Selection(
        RESULTADOS_TELEVENTAS, string='Resultado televentas', readonly=True)
    monto_venta_televentas = fields.Monetary(
        string='Monto venta televentas', currency_field='currency_id',
        readonly=True)
    proxima_accion_televentas_id = fields.Many2one(
        'sng.visita.catalogo', string='Próxima acción televentas',
        readonly=True)
    fecha_proxima_accion_televentas = fields.Date(
        string='Fecha próxima acción televentas', readonly=True)
    comentario_televentas = fields.Text(
        string='Comentario televentas', readonly=True)

    # ---- calculados (AC..AI del Excel)
    estado_atencion = fields.Selection(
        ESTADOS_ATENCION, string='Estado de atención', readonly=True,
        index=True)
    dias_sin_facturar = fields.Integer(
        string='Días sin facturar', readonly=True)
    nunca_facturo = fields.Boolean(string='Nunca facturó', readonly=True)
    efectividad_visita = fields.Float(
        string='Efectividad visita', readonly=True, digits=(3, 2))
    efectividad_televentas = fields.Float(
        string='Efectividad televentas', readonly=True, digits=(3, 2))
    cliente_desatendido = fields.Boolean(
        string='Cliente desatendido', readonly=True)
    responsable_proximo_paso = fields.Selection(
        RESPONSABLES, string='Responsable próximo paso', readonly=True)
    alerta_gerencial = fields.Selection(
        ALERTAS, string='Alerta gerencial', readonly=True, index=True)
    alerta_orden = fields.Integer(string='Orden alerta', readonly=True)

    # ---- indicadores 0/1 (sumables en pivot)
    total = fields.Integer(string='Clientes', readonly=True, default=1)
    es_visitado = fields.Integer(string='Visitados', readonly=True)
    es_solo_televentas = fields.Integer(
        string='Solo televentas', readonly=True)
    es_pendiente_visita = fields.Integer(
        string='Pendiente visita', readonly=True)
    es_sin_gestion = fields.Integer(string='Sin gestión', readonly=True)
    es_desatendido = fields.Integer(string='Sin atención', readonly=True)
    es_venta_facturada = fields.Integer(
        string='Ventas por visita', readonly=True)
    es_venta_recuperada = fields.Integer(
        string='Ventas recuperadas', readonly=True)
    es_contacto_televentas = fields.Integer(
        string='Contactos televentas', readonly=True)
    es_seguimiento_vencido = fields.Integer(
        string='Seguimientos vencidos', readonly=True)
    es_mas_90_dias = fields.Integer(
        string='Más de N días sin facturar', readonly=True)
    es_pendiente_agente = fields.Integer(
        string='Pendientes del agente', readonly=True)
    es_pendiente_televentas = fields.Integer(
        string='Pendientes de televentas', readonly=True)
    es_pendiente_compartido = fields.Integer(
        string='Pendientes compartidos', readonly=True)
    registros_sin_comentario = fields.Integer(
        string='Registros sin comentario', readonly=True)

    _sql_constraints = [
        ('partner_periodo_uniq',
         'unique(partner_id, periodo, company_id)',
         'Ya existe una línea de la matriz para este cliente y período.'),
    ]

    # ================================================================ período

    @staticmethod
    def _sng_rango_mes(fecha):
        desde = fecha.replace(day=1)
        hasta = fecha.replace(
            day=calendar.monthrange(fecha.year, fecha.month)[1])
        return desde, hasta

    @api.model
    def _sng_generar_mes(self, fecha, company=None):
        desde, hasta = self._sng_rango_mes(fecha)
        return self._sng_generar_periodo(
            desde, hasta, company or self.env.company)

    # ============================================================== maestros

    @api.model
    def _sng_clientes_maestros(self, company):
        """Población de la matriz: clientes activos con ventas, misma base
        que el Reporte Clientes por Ruta pero sin excluir a los que también
        son proveedores (varios clientes grandes lo son).

        Se excluyen los clientes con crédito bloqueado desde CxC (cerrados
        por mora): no se les puede vender, así que no deben aparecer como
        pendientes de visita ni generar seguimientos de televentas. Tampoco
        entran los marcados para excluir (clientes genéricos de tiquete) ni
        el contacto de las propias compañías.

        Multi-compañía (Grupo Famoso): los clientes son compartidos entre
        las compañías, así que la matriz de cada compañía solo incluye a
        los que le han comprado alguna vez (factura publicada en esa
        compañía) o son exclusivos de ella. Con ``partner_multi_company``
        (OCA) ``company_id`` es un cálculo sobre ``company_ids`` y devuelve
        la compañía activa para casi todos los clientes, así que "exclusivo"
        se mide con ``company_ids == compañía``. El agente asignado por
        compañía tampoco sirve de filtro: está cargado masivamente en
        clientes que nunca han comprado. Sin este filtro cada compañía
        tendría miles de clientes "sin atención" que en realidad son de otra."""
        Partner = self.env['res.partner']
        companias = self.env['res.company'].sudo().search([]).partner_id
        partners = Partner.search([
            ('customer_rank', '>', 0),
            ('active', '=', True),
            ('type', '=', 'contact'),
            ('parent_id', '=', False),
            ('is_salesperson', '=', False),
            ('user_ids', '=', False),
            ('sng_credit_blocked', '=', False),
            ('sng_excluir_matriz', '=', False),
            ('id', 'not in', companias.ids),
            '|', ('company_id', '=', company.id), ('company_id', '=', False),
        ])
        if not partners:
            return partners, {}
        self.env.cr.execute("""
            SELECT commercial_partner_id, MAX(invoice_date)
              FROM account_move
             WHERE move_type = 'out_invoice'
               AND state = 'posted'
               AND invoice_date IS NOT NULL
               AND company_id = %s
               AND commercial_partner_id = ANY(%s)
             GROUP BY commercial_partner_id
        """, (company.id, list(partners.ids)))
        ultimas = dict(self.env.cr.fetchall())
        if 'company_ids' in Partner._fields:
            def exclusivo(p):
                return p.company_ids == company
        else:
            def exclusivo(p):
                return p.company_id == company
        partners = partners.filtered(
            lambda p: p.id in ultimas or exclusivo(p))
        return partners, ultimas

    def _sng_vals_maestros(self, partner, company, ultima_factura):
        partner = partner.with_company(company)
        plazo = partner.property_payment_term_id
        lista = partner.property_product_pricelist
        return {
            'unique_id': partner.unique_id or '',
            'name': partner.name or '',
            'commercial_name': partner.commercial_name or partner.name or '',
            'route_code': partner.sales_route_id.code or '',
            'sales_route_id': partner.sales_route_id.id,
            'vendedor_id': partner.assigned_salesperson_id.id,
            'phone': partner.phone or partner.mobile or '',
            'payment_term_name': plazo.name or '',
            'pricelist_name': lista.name or '',
            'last_invoice_date': ultima_factura or False,
            'address': partner.contact_address_complete or '',
            'tipo_atencion': partner.sng_tipo_atencion or 'ruta',
            'frecuencia_visita': partner.sng_frecuencia_visita or 'mensual',
        }

    # ============================================================ generación

    @api.model
    def _sng_generar_periodo(self, fecha_desde, fecha_hasta, company):
        """Regenera (crea o actualiza) todas las líneas de un período."""
        hoy = fields.Date.context_today(self)
        corte = min(hoy, fecha_hasta)
        periodo = fecha_desde.strftime('%Y-%m')
        dias_alerta = company.sng_control_visitas_dias_alerta_factura or 90

        partners, ultimas = self._sng_clientes_maestros(company)

        Visita = self.env['sng.ruteros.visita']
        Seg = self.env['sng.televentas.seguimiento']
        ini_dt = fields.Datetime.to_datetime(fecha_desde) - timedelta(days=1)
        fin_dt = fields.Datetime.to_datetime(fecha_hasta) + timedelta(days=2)
        visitas = Visita.search([
            ('partner_id', 'in', partners.ids),
            ('company_id', '=', company.id),
            ('fecha_inicio', '>=', ini_dt),
            ('fecha_inicio', '<=', fin_dt),
        ], order='fecha_inicio desc, id desc')
        v_ultima, v_real, v_programadas = {}, {}, {}
        for v in visitas:
            fecha = v._sng_fecha_visita()
            if not (fecha_desde <= fecha <= fecha_hasta):
                continue
            pid = v.partner_id.id
            v_ultima.setdefault(pid, v)
            if v._es_visita_real():
                v_real.setdefault(pid, v)
            if v.fecha_programada:
                v_programadas.setdefault(pid, []).append(v.fecha_programada)

        seg_real = {}
        for s in Seg.search([
                ('partner_id', 'in', partners.ids),
                ('company_id', '=', company.id),
                ('estado', '=', 'realizado'),
                ('fecha_seguimiento', '>=', fecha_desde),
                ('fecha_seguimiento', '<=', fecha_hasta),
        ], order='fecha_seguimiento desc, id desc'):
            seg_real.setdefault(s.partner_id.id, s)
        seg_pend = {}
        for s in Seg.search([
                ('partner_id', 'in', partners.ids),
                ('company_id', '=', company.id),
                ('estado', '=', 'pendiente'),
                ('semana', '<=', fecha_hasta),
        ], order='semana desc, id desc'):
            seg_pend.setdefault(s.partner_id.id, s)

        existentes = {
            l.partner_id.id: l for l in self.search([
                ('periodo', '=', periodo), ('company_id', '=', company.id)])}

        ahora = fields.Datetime.now()
        a_crear = []
        for partner in partners:
            pid = partner.id
            vals = self._sng_vals_maestros(partner, company, ultimas.get(pid))
            vals.update(self._sng_vals_gestion(
                partner, vals, v_ultima.get(pid), v_real.get(pid),
                v_programadas.get(pid), seg_real.get(pid), seg_pend.get(pid),
                fecha_desde, fecha_hasta, corte, dias_alerta))
            vals.update({
                'periodo': periodo,
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta,
                'fecha_corte': corte,
                'fecha_generacion': ahora,
                'company_id': company.id,
                'partner_id': pid,
            })
            linea = existentes.pop(pid, None)
            if linea:
                linea.write(vals)
            else:
                a_crear.append(vals)
        creadas = self.create(a_crear) if a_crear else self.browse()
        # Clientes archivados o que dejaron de ser clientes.
        if existentes:
            self.browse([l.id for l in existentes.values()]).unlink()
        _logger.info(
            'sng_control_visitas: matriz %s %s regenerada (%s clientes)',
            periodo, company.name, len(partners))
        return creadas

    @api.model
    def _sng_vals_gestion(self, partner, maestros, v_ult, v_real,
                          programadas, s_real, s_pend, fecha_desde,
                          fecha_hasta, corte, dias_alerta):
        """Bloques agente/televentas y columnas AC..AI del Excel."""
        tipo = maestros['tipo_atencion']
        frecuencia = maestros['frecuencia_visita']
        dias_frec = DIAS_FRECUENCIA.get(frecuencia)
        nunca_visitado = not partner.sng_fecha_ultima_visita

        realizada = v_real._sng_fecha_visita() if v_real else False
        fecha_seg = s_real.fecha_seguimiento if s_real else False

        # ---- visita programada (columna M). Una visita realizada implica
        # que estaba programada; si no, se deduce de la frecuencia.
        programada = min(programadas) if programadas else False
        if not programada and realizada:
            programada = realizada
        if not programada and tipo == 'ruta' and dias_frec:
            proxima = partner.sng_fecha_proxima_visita
            if nunca_visitado:
                programada = fecha_desde
            elif proxima and proxima <= fecha_hasta:
                programada = max(proxima, fecha_desde)

        # ---- próximas acciones abiertas (S y AA)
        accion_agente = (
            v_ult.fecha_proxima_accion
            if v_ult and not v_ult.accion_cerrada else False)
        accion_tv = (
            s_real.fecha_proxima_accion
            if s_real and not s_real.accion_cerrada else False)

        # ---- AC estado de atención
        if not programada and not fecha_seg:
            estado = 'sin_gestion'
        elif realizada:
            estado = 'visitado'
        elif fecha_seg:
            estado = 'solo_televentas'
        else:
            estado = 'pendiente_visita'

        # ---- AD días sin facturar
        ultima_factura = maestros['last_invoice_date']
        dias = (corte - ultima_factura).days if ultima_factura else 0

        # ---- AE / AF efectividad
        resultado_visita = v_ult.resultado_comercial if v_ult else False
        resultado_tv = s_real.resultado if s_real else False
        ef_visita = EFECTIVIDAD_VISITA.get(resultado_visita, 0.0)
        ef_tv = EFECTIVIDAD_TELEVENTAS.get(resultado_tv, 0.0)

        # ---- AG cliente desatendido (fórmula del Excel + frecuencia)
        if tipo == 'ruta':
            esperado = bool(dias_frec) and (bool(programada) or nunca_visitado)
        else:
            ultimo = partner.sng_fecha_ultimo_contacto_televentas
            esperado = (frecuencia != 'sin_visita') and (
                not ultimo
                or not dias_frec
                or ultimo + timedelta(days=dias_frec) <= fecha_hasta)
        desatendido = bool(not realizada and not fecha_seg and esperado)

        # ---- AH responsable próximo paso
        if desatendido:
            responsable = 'ambos'
        elif accion_agente and accion_agente <= corte:
            responsable = 'agente'
        elif accion_tv and accion_tv <= corte:
            responsable = 'televentas'
        else:
            responsable = 'sin_accion'

        # ---- AI alerta gerencial
        if desatendido:
            alerta = 'sin_atencion'
        elif ultima_factura and dias > dias_alerta:
            alerta = 'mas_90_dias'
        elif ((accion_agente and accion_agente < corte)
              or (accion_tv and accion_tv < corte)):
            alerta = 'seguimiento_vencido'
        else:
            alerta = 'ok'

        sin_comentario = int(bool(realizada and v_real.sin_comentario)) + \
            int(bool(fecha_seg and s_real.sin_comentario))

        return {
            'visita_id': v_ult.id if v_ult else False,
            'fecha_visita_programada': programada or False,
            'fecha_visita_realizada': realizada or False,
            'resultado_visita': resultado_visita,
            'monto_venta_visita': v_ult.monto_venta if v_ult else 0.0,
            'motivo_sin_venta_id': v_ult.motivo_sin_venta_id.id if v_ult else False,
            'proxima_accion_agente_id': v_ult.proxima_accion_id.id if v_ult else False,
            'fecha_proxima_accion_agente': v_ult.fecha_proxima_accion if v_ult else False,
            'comentario_agente': (
                (v_ult.comentario_agente or v_ult.comentario_tipo_id.name
                 or v_ult.observaciones) if v_ult else False),
            'requiere_seguimiento_televentas': bool(
                v_ult and v_ult.requiere_seguimiento_televentas),
            'seguimiento_id': s_real.id if s_real else False,
            'seguimiento_pendiente_id': s_pend.id if s_pend else False,
            'fecha_seguimiento': fecha_seg or False,
            'canal': s_real.canal if s_real else False,
            'resultado_televentas': resultado_tv,
            'monto_venta_televentas': s_real.monto_venta if s_real else 0.0,
            'proxima_accion_televentas_id': s_real.proxima_accion_id.id if s_real else False,
            'fecha_proxima_accion_televentas': s_real.fecha_proxima_accion if s_real else False,
            'comentario_televentas': (
                (s_real.comentario or s_real.comentario_tipo_id.name)
                if s_real else False),
            'estado_atencion': estado,
            'dias_sin_facturar': dias,
            'nunca_facturo': not ultima_factura,
            'efectividad_visita': ef_visita,
            'efectividad_televentas': ef_tv,
            'cliente_desatendido': desatendido,
            'responsable_proximo_paso': responsable,
            'alerta_gerencial': alerta,
            'alerta_orden': ALERTA_ORDEN[alerta],
            'total': 1,
            'es_visitado': int(estado == 'visitado'),
            'es_solo_televentas': int(estado == 'solo_televentas'),
            'es_pendiente_visita': int(estado == 'pendiente_visita'),
            'es_sin_gestion': int(estado == 'sin_gestion'),
            'es_desatendido': int(desatendido),
            'es_venta_facturada': int(resultado_visita == 'venta_facturada'),
            'es_venta_recuperada': int(resultado_tv == 'venta_recuperada'),
            'es_contacto_televentas': int(bool(fecha_seg)),
            'es_seguimiento_vencido': int(alerta == 'seguimiento_vencido'),
            'es_mas_90_dias': int(alerta == 'mas_90_dias'),
            'es_pendiente_agente': int(responsable == 'agente'),
            'es_pendiente_televentas': int(responsable == 'televentas'),
            'es_pendiente_compartido': int(responsable == 'ambos'),
            'registros_sin_comentario': sin_comentario,
        }

    # ================================================================== KPIs

    @api.model
    def _sng_kpis(self, periodo, company):
        campos = [
            'total', 'es_visitado', 'es_solo_televentas',
            'es_pendiente_visita', 'es_sin_gestion', 'es_desatendido',
            'es_venta_facturada', 'es_venta_recuperada',
            'es_contacto_televentas', 'es_seguimiento_vencido',
            'es_mas_90_dias', 'es_pendiente_agente',
            'es_pendiente_televentas', 'es_pendiente_compartido',
            'registros_sin_comentario', 'monto_venta_visita',
            'monto_venta_televentas',
        ]
        grupos = self.read_group(
            [('periodo', '=', periodo), ('company_id', '=', company.id)],
            [f'{c}:sum' for c in campos], [])
        suma = {c: (grupos[0].get(c) or 0) for c in campos} if grupos else {
            c: 0 for c in campos}

        def pct(num, den):
            return round(num / den, 4) if den else 0.0

        total = suma['total']
        return {
            'periodo': periodo,
            'total_clientes': total,
            'clientes_visitados': suma['es_visitado'],
            'clientes_solo_televentas': suma['es_solo_televentas'],
            'clientes_pendiente_visita': suma['es_pendiente_visita'],
            'clientes_sin_atencion': suma['es_desatendido'],
            'ventas_por_visita': suma['es_venta_facturada'],
            'ventas_recuperadas': suma['es_venta_recuperada'],
            'monto_ventas_visita': suma['monto_venta_visita'],
            'monto_ventas_televentas': suma['monto_venta_televentas'],
            'pct_cobertura_visitas': pct(suma['es_visitado'], total),
            'pct_atencion_total': pct(total - suma['es_desatendido'], total),
            'pct_conversion_visita': pct(
                suma['es_venta_facturada'], suma['es_visitado']),
            'pct_conversion_televentas': pct(
                suma['es_venta_recuperada'], suma['es_contacto_televentas']),
            'pct_clientes_sin_atencion': pct(suma['es_desatendido'], total),
            'pct_recuperacion_no_visitados': pct(
                suma['es_venta_recuperada'], suma['es_pendiente_visita']),
            'seguimientos_vencidos': suma['es_seguimiento_vencido'],
            'clientes_mas_90_dias': suma['es_mas_90_dias'],
            'pendientes_agente': suma['es_pendiente_agente'],
            'pendientes_televentas': suma['es_pendiente_televentas'],
            'pendientes_compartidos': suma['es_pendiente_compartido'],
            'registros_sin_comentario': suma['registros_sin_comentario'],
        }

    # ================================================================= crons

    @api.model
    def _sng_cron_recalcular_matriz(self):
        hoy = fields.Date.context_today(self)
        for company in self.env['res.company'].search([]):
            self._sng_generar_mes(hoy, company)
            if hoy.day <= 5:
                mes_anterior = hoy.replace(day=1) - timedelta(days=1)
                self._sng_generar_mes(mes_anterior, company)
        return True

    @api.model
    def _sng_cron_generar_pendientes(self):
        """Crea los pendientes de televentas de la semana que empieza.

        Corre el domingo (Grupo Famoso) o el lunes: la semana objetivo es
        la del lunes siguiente si hoy es domingo, o la actual en cualquier
        otro día. Así el domingo a las 06:00 los pendientes quedan listos
        para el lunes y "semana previa" es la que acaba de terminar."""
        Seg = self.env['sng.televentas.seguimiento']
        Visita = self.env['sng.ruteros.visita']
        hoy = fields.Date.context_today(self)
        semana = Seg._sng_lunes(hoy + timedelta(days=1))
        prev_ini = semana - timedelta(days=7)
        prev_fin = semana - timedelta(days=1)

        for company in self.env['res.company'].search([]):
            partners, ultimas = self._sng_clientes_maestros(company)
            con_pendiente = set(Seg.search([
                ('company_id', '=', company.id),
                ('estado', '=', 'pendiente'),
            ]).mapped('partner_id').ids)
            recientes = set(Seg.search([
                ('company_id', '=', company.id),
                ('estado', '=', 'realizado'),
                ('fecha_seguimiento', '>=', hoy - timedelta(days=7)),
            ]).mapped('partner_id').ids)
            excluidos = con_pendiente | recientes
            candidatos = {}  # partner_id -> (origen, visita)

            # a) visitas de la semana previa que piden televentas
            visitas = Visita.search([
                ('company_id', '=', company.id),
                ('partner_id', 'in', partners.ids),
                ('fecha_inicio', '>=', fields.Datetime.to_datetime(prev_ini)),
                ('fecha_inicio', '<', fields.Datetime.to_datetime(
                    semana + timedelta(days=1))),
            ], order='fecha_inicio desc')
            for v in visitas:
                fecha = v._sng_fecha_visita()
                if not (prev_ini <= fecha <= prev_fin):
                    continue
                pid = v.partner_id.id
                if pid in excluidos or pid in candidatos:
                    continue
                if v.requiere_seguimiento_televentas or not v._es_visita_real():
                    if v.seguimiento_ids:
                        continue
                    origen = ('solicitud_agente'
                              if v.requiere_seguimiento_televentas
                              else 'no_visitado')
                    candidatos[pid] = (origen, v)

            visitados_prev = set()
            for v in visitas:
                if v._es_visita_real():
                    visitados_prev.add(v.partner_id.id)

            limite_inactivo = hoy - timedelta(days=365)
            for partner in partners:
                pid = partner.id
                if pid in excluidos or pid in candidatos:
                    continue
                tipo = partner.sng_tipo_atencion or 'ruta'
                frec = partner.sng_frecuencia_visita or 'mensual'
                dias = DIAS_FRECUENCIA.get(frec)
                if frec == 'sin_visita':
                    continue
                if tipo == 'ruta':
                    # b) visita esperada y vencida sin visita real
                    proxima = partner.sng_fecha_proxima_visita
                    ultima_factura = ultimas.get(pid)
                    if pid in visitados_prev:
                        continue
                    if proxima and proxima <= prev_fin:
                        candidatos[pid] = ('visita_pendiente', Visita)
                    elif (not partner.sng_fecha_ultima_visita
                          and ultima_factura
                          and ultima_factura >= limite_inactivo):
                        candidatos[pid] = ('visita_pendiente', Visita)
                else:
                    # c) contacto de televentas vencido según frecuencia
                    ultimo = partner.sng_fecha_ultimo_contacto_televentas
                    if not dias:
                        continue
                    if not ultimo or ultimo + timedelta(days=dias) <= prev_fin:
                        candidatos[pid] = ('frecuencia_televentas', Visita)

            vals_list = [{
                'partner_id': pid,
                'company_id': company.id,
                'visita_id': visita.id if visita else False,
                'origen': origen,
                'semana': semana,
            } for pid, (origen, visita) in candidatos.items()]
            creados = Seg.create(vals_list) if vals_list else Seg
            conteo = {}
            for origen, _v in candidatos.values():
                conteo[origen] = conteo.get(origen, 0) + 1
            _logger.info(
                'sng_control_visitas: %s pendientes de televentas creados '
                'para %s semana %s (%s)', len(creados), company.name,
                semana, conteo)
            self._sng_publicar(company, Markup(
                '<p><b>%s</b><br/>%s</p>') % (
                _('📞 Televentas — semana del %(semana)s — %(comp)s',
                  semana=semana.strftime('%d/%m/%Y'), comp=company.name),
                _('%(n)s seguimientos pendientes generados '
                  '(no visitados: %(a)s, visita pendiente: %(b)s, '
                  'solicitud del agente: %(c)s, frecuencia televentas: %(d)s).',
                  n=len(creados),
                  a=conteo.get('no_visitado', 0),
                  b=conteo.get('visita_pendiente', 0),
                  c=conteo.get('solicitud_agente', 0),
                  d=conteo.get('frecuencia_televentas', 0))))
        return True

    @api.model
    def _sng_cron_resumen_gerencial(self):
        hoy = fields.Date.context_today(self)
        for company in self.env['res.company'].search([]):
            self._sng_generar_mes(hoy, company)
            periodo = hoy.strftime('%Y-%m')
            k = self._sng_kpis(periodo, company)
            self._sng_publicar(company, self._sng_html_resumen(
                company, hoy, periodo, k))
        return True

    def _sng_html_resumen(self, company, hoy, periodo, k):
        def fila(etq, val):
            return Markup('<tr><td>%s</td><td style="text-align:right">'
                          '<b>%s</b></td></tr>') % (etq, val)

        def p(v):
            return '%.1f%%' % (v * 100)

        moneda = company.currency_id

        def m(v):
            return moneda.format(v or 0.0)
        tabla = Markup('<table class="table table-sm"><tbody>%s</tbody></table>') % (
            fila(_('Total clientes'), k['total_clientes'])
            + fila(_('Clientes visitados'), k['clientes_visitados'])
            + fila(_('Clientes solo televentas'), k['clientes_solo_televentas'])
            + fila(_('Clientes sin atención'), k['clientes_sin_atencion'])
            + fila(_('% cobertura de visitas'), p(k['pct_cobertura_visitas']))
            + fila(_('% atención total'), p(k['pct_atencion_total']))
            + fila(_('% conversión de visita'), p(k['pct_conversion_visita']))
            + fila(_('% conversión televentas'), p(k['pct_conversion_televentas']))
            + fila(_('Ventas por visita'), k['ventas_por_visita'])
            + fila(_('Ventas recuperadas televentas'), k['ventas_recuperadas'])
            + fila(_('Monto ventas por visita'), m(k['monto_ventas_visita']))
            + fila(_('Monto ventas televentas'), m(k['monto_ventas_televentas']))
            + fila(_('Seguimientos vencidos'), k['seguimientos_vencidos'])
            + fila(_('Clientes >%s días sin facturar') % (
                company.sng_control_visitas_dias_alerta_factura or 90),
                k['clientes_mas_90_dias'])
            + fila(_('Pendientes del agente'), k['pendientes_agente'])
            + fila(_('Pendientes de televentas'), k['pendientes_televentas'])
            + fila(_('Pendientes compartidos'), k['pendientes_compartidos'])
            + fila(_('Registros sin comentario'), k['registros_sin_comentario'])
        )
        secciones = Markup('')
        for alerta, titulo in (('sin_atencion', _('Clientes sin atención')),
                               ('seguimiento_vencido', _('Seguimientos vencidos'))):
            lineas = self.search([
                ('periodo', '=', periodo), ('company_id', '=', company.id),
                ('alerta_gerencial', '=', alerta)],
                order='vendedor_id, commercial_name', limit=15)
            if not lineas:
                continue
            items = Markup('').join(
                Markup('<li>%s — %s</li>') % (
                    escape(l.vendedor_id.name or _('Sin agente')),
                    escape(l.commercial_name or l.name or ''))
                for l in lineas)
            secciones += Markup('<p><b>%s (top %s)</b></p><ul>%s</ul>') % (
                titulo, len(lineas), items)
        return Markup('<p><b>%s</b></p>%s%s') % (
            _('📊 Control de visitas — %(comp)s — %(periodo)s al %(fecha)s',
              comp=company.name, periodo=periodo,
              fecha=hoy.strftime('%d/%m/%Y')),
            tabla, secciones)

    def _sng_publicar(self, company, body):
        channel = self.env.ref(
            'sng_control_visitas.channel_control_visitas',
            raise_if_not_found=False)
        if channel is None:
            _logger.warning('sng_control_visitas: canal de Discuss no existe')
            return
        channel.sudo().message_post(
            body=body, message_type='comment',
            subtype_xmlid='mail.mt_comment')

    # ============================================================== acciones

    def action_abrir_visita(self):
        self.ensure_one()
        if not self.visita_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sng.ruteros.visita',
            'res_id': self.visita_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_abrir_seguimiento(self):
        self.ensure_one()
        seg = self.seguimiento_pendiente_id or self.seguimiento_id
        if not seg:
            return self.action_crear_seguimiento()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sng.televentas.seguimiento',
            'res_id': seg.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_crear_seguimiento(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sng.televentas.seguimiento',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_company_id': self.company_id.id,
                'default_visita_id': self.visita_id.id,
                'default_origen': 'manual',
            },
        }

    def action_recalcular_periodo(self):
        periodos = {(l.fecha_desde, l.fecha_hasta, l.company_id) for l in self}
        if not periodos:
            hoy = fields.Date.context_today(self)
            desde, hasta = self._sng_rango_mes(hoy)
            periodos = {(desde, hasta, self.env.company)}
        for desde, hasta, company in periodos:
            self._sng_generar_periodo(desde, hasta, company)
        return True
