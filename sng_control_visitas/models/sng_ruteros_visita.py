# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

from .sng_visita_catalogo import (
    CODIGO_CERRAR_SEGUIMIENTO, CODIGO_TRANSFERIR_TELEVENTAS)

_logger = logging.getLogger(__name__)

RESULTADOS_COMERCIALES = [
    ('venta_facturada', 'Venta facturada'),
    ('pedido_pendiente', 'Pedido pendiente'),
    ('cotizacion_enviada', 'Cotización enviada'),
    ('sin_venta', 'Sin venta'),
    ('no_visitado', 'No visitado'),
    ('visita_reprogramada', 'Visita reprogramada'),
    ('cliente_cerrado', 'Cliente cerrado'),
    ('bloqueado_cobro', 'Bloqueado por cobro'),
    ('revision_inventario', 'Revisión de inventario'),
    ('visita_bimensual', 'Visita bimensual'),
]

# Efectividad de visita según la guía: 100% venta facturada; 50% pedido
# pendiente o cotización; 0% sin resultado comercial.
EFECTIVIDAD_VISITA = {
    'venta_facturada': 1.0,
    'pedido_pendiente': 0.5,
    'cotizacion_enviada': 0.5,
}

RESULTADOS_NO_VISITA = ('no_visitado', 'visita_reprogramada')

# Claves que la app puede mandar con el código del catálogo en vez del id.
CAMPOS_CODIGO = {
    'motivo_sin_venta_codigo': ('motivo_sin_venta_id', 'motivo_sin_venta'),
    'proxima_accion_codigo': ('proxima_accion_id', 'proxima_accion'),
    'comentario_tipo_codigo': ('comentario_tipo_id', 'comentario_agente'),
}


class SngRuterosVisita(models.Model):
    """Bloque comercial del agente sobre la visita que manda la app.

    `resultado` (visita/venta/cobro) sigue siendo el dato técnico de la app;
    `resultado_comercial` es la lectura de negocio de la matriz gerencial.
    """

    _inherit = 'sng.ruteros.visita'

    fecha_programada = fields.Date(
        string='Fecha visita programada',
        help='Fecha en que estaba planificada la visita (opcional).',
    )
    resultado_comercial = fields.Selection(
        RESULTADOS_COMERCIALES,
        string='Resultado de visita',
        compute='_compute_resultado_comercial',
        store=True,
        readonly=False,
        index=True,
        help='Se deduce del resultado de la app y de la facturación de la '
             'orden; el agente o televentas pueden fijarlo explícitamente.',
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda')
    monto_venta = fields.Monetary(
        string='Monto venta visita',
        currency_field='currency_id',
        compute='_compute_monto_venta',
        store=True,
        readonly=False,
    )
    motivo_sin_venta_id = fields.Many2one(
        'sng.visita.catalogo',
        string='Motivo sin venta',
        domain="[('tipo', '=', 'motivo_sin_venta')]",
        ondelete='restrict',
    )
    proxima_accion_id = fields.Many2one(
        'sng.visita.catalogo',
        string='Próxima acción agente',
        domain="[('tipo', '=', 'proxima_accion')]",
        ondelete='restrict',
    )
    fecha_proxima_accion = fields.Date(string='Fecha próxima acción')
    comentario_tipo_id = fields.Many2one(
        'sng.visita.catalogo',
        string='Comentario predeterminado',
        domain="[('tipo', '=', 'comentario_agente')]",
        ondelete='restrict',
    )
    comentario_agente = fields.Text(string='Comentario agente')
    requiere_seguimiento_televentas = fields.Boolean(
        string='Requiere seguimiento televentas',
        compute='_compute_requiere_seguimiento',
        store=True,
        readonly=False,
        help='Televentas debe contactar al cliente la semana siguiente.',
    )
    accion_cerrada = fields.Boolean(
        string='Acción cerrada',
        default=False,
        help='La próxima acción de esta visita ya fue atendida (por una '
             'visita posterior, un seguimiento o cierre manual).',
    )
    seguimiento_ids = fields.One2many(
        'sng.televentas.seguimiento', 'visita_id',
        string='Seguimientos televentas')
    seguimiento_count = fields.Integer(
        compute='_compute_seguimiento_count')
    sin_comentario = fields.Boolean(
        string='Sin comentario',
        compute='_compute_sin_comentario',
        store=True,
    )
    efectividad = fields.Float(
        string='Efectividad visita',
        compute='_compute_efectividad',
        store=True,
        digits=(3, 2),
    )
    sales_route_id = fields.Many2one(
        related='partner_id.sales_route_id', string='Ruta', store=True)

    # ----------------------------------------------------------------- computes

    @api.depends('resultado', 'sale_order_id.invoice_status',
                 'sale_order_id.state')
    def _compute_resultado_comercial(self):
        for rec in self:
            actual = rec.resultado_comercial
            # Un valor explícito se respeta; solo "pedido pendiente" se
            # promueve a "venta facturada" cuando la orden queda facturada.
            if actual and actual != 'pedido_pendiente':
                continue
            if rec.resultado in ('venta', 'venta_cobro'):
                facturada = rec.sale_order_id.invoice_status == 'invoiced'
                rec.resultado_comercial = (
                    'venta_facturada' if facturada else 'pedido_pendiente')
            elif not actual:
                rec.resultado_comercial = 'sin_venta'

    @api.depends('sale_order_id.amount_total', 'resultado_comercial')
    def _compute_monto_venta(self):
        for rec in self:
            if rec.monto_venta:
                continue
            if (rec.sale_order_id
                    and rec.resultado_comercial in ('venta_facturada',
                                                    'pedido_pendiente')):
                rec.monto_venta = rec.sale_order_id.amount_total
            else:
                rec.monto_venta = rec.monto_venta or 0.0

    @api.depends('proxima_accion_id', 'resultado_comercial')
    def _compute_requiere_seguimiento(self):
        for rec in self:
            if rec.requiere_seguimiento_televentas:
                continue  # un "Sí" manual no se pisa
            rec.requiere_seguimiento_televentas = bool(
                rec.proxima_accion_id.codigo == CODIGO_TRANSFERIR_TELEVENTAS
                or rec.resultado_comercial in RESULTADOS_NO_VISITA)

    @api.depends('seguimiento_ids')
    def _compute_seguimiento_count(self):
        for rec in self:
            rec.seguimiento_count = len(rec.seguimiento_ids)

    @api.depends('resultado_comercial', 'comentario_tipo_id',
                 'comentario_agente', 'observaciones')
    def _compute_sin_comentario(self):
        for rec in self:
            rec.sin_comentario = bool(
                rec._es_visita_real()
                and not rec.comentario_tipo_id
                and not (rec.comentario_agente or '').strip()
                and not (rec.observaciones or '').strip())

    @api.depends('resultado_comercial')
    def _compute_efectividad(self):
        for rec in self:
            rec.efectividad = EFECTIVIDAD_VISITA.get(
                rec.resultado_comercial, 0.0)

    # ------------------------------------------------------------------ helpers

    def _es_visita_real(self):
        """Visita que sí se realizó (cuenta para cobertura)."""
        self.ensure_one()
        return self.resultado_comercial not in RESULTADOS_NO_VISITA

    def _sng_fecha_visita(self):
        self.ensure_one()
        if not self.fecha_inicio:
            return False
        return fields.Datetime.context_timestamp(
            self, self.fecha_inicio).date()

    @api.model
    def _sng_resolver_codigos(self, vals):
        """La app puede mandar `proxima_accion_codigo` etc. en lugar del id
        del catálogo, para no depender de ids entre entornos."""
        Catalogo = self.env['sng.visita.catalogo']
        for clave, (campo, tipo) in CAMPOS_CODIGO.items():
            if clave not in vals:
                continue
            codigo = vals.pop(clave)
            if vals.get(campo):
                continue
            rec = Catalogo._sng_buscar_codigo(tipo, codigo)
            if rec:
                vals[campo] = rec.id
            elif codigo:
                _logger.warning(
                    'sng.ruteros.visita: código de catálogo desconocido '
                    '%s=%r; se ignora', clave, codigo)

    def _sng_cerrar_acciones_previas(self):
        """Una visita nueva cierra la próxima acción abierta de las visitas
        anteriores del mismo cliente (regla "sin cierre registrado")."""
        for rec in self:
            previas = self.search([
                ('partner_id', '=', rec.partner_id.id),
                ('id', '!=', rec.id),
                ('accion_cerrada', '=', False),
                ('fecha_proxima_accion', '!=', False),
                ('fecha_inicio', '<=', rec.fecha_inicio),
            ])
            if previas:
                previas.write({'accion_cerrada': True})

    def _sng_crear_seguimiento_pendiente(self, origen='solicitud_agente'):
        """Crea el pendiente de televentas para la semana siguiente a la
        visita, si el cliente no tiene ya uno abierto."""
        Seguimiento = self.env['sng.televentas.seguimiento']
        creados = Seguimiento.browse()
        for rec in self:
            if rec.seguimiento_ids.filtered(lambda s: s.estado == 'pendiente'):
                continue
            fecha = rec._sng_fecha_visita() or fields.Date.context_today(rec)
            semana = Seguimiento._sng_lunes(fecha) + Seguimiento._SEMANA
            abierto = Seguimiento.search([
                ('partner_id', '=', rec.partner_id.id),
                ('company_id', '=', rec.company_id.id),
                ('estado', '=', 'pendiente'),
            ], limit=1)
            if abierto:
                if not abierto.visita_id:
                    abierto.visita_id = rec
                continue
            creados |= Seguimiento.create({
                'partner_id': rec.partner_id.id,
                'company_id': rec.company_id.id,
                'visita_id': rec.id,
                'origen': origen,
                'semana': semana,
            })
        return creados

    # --------------------------------------------------------------------- ORM

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sng_resolver_codigos(vals)
        # El módulo base devuelve la visita existente cuando la app reintenta
        # con el mismo sng_uuid: el post-proceso solo aplica a las nuevas.
        uuids = [(v.get('sng_uuid') or '').strip() for v in vals_list]
        existentes = set()
        if any(uuids):
            existentes = set(self.sudo().search([
                ('sng_uuid', 'in', [u for u in uuids if u])]).ids)
        visitas = super().create(vals_list)
        nuevas = visitas.filtered(lambda v: v.id not in existentes)
        if nuevas:
            nuevas._sng_cerrar_acciones_previas()
            nuevas.filtered('requiere_seguimiento_televentas') \
                ._sng_crear_seguimiento_pendiente()
        return visitas

    def write(self, vals):
        if 'proxima_accion_codigo' in vals or any(
                k in vals for k in CAMPOS_CODIGO):
            self._sng_resolver_codigos(vals)
        res = super().write(vals)
        if vals.get('proxima_accion_id'):
            accion = self.env['sng.visita.catalogo'].browse(
                vals['proxima_accion_id'])
            if accion.codigo == CODIGO_CERRAR_SEGUIMIENTO:
                super().write({'accion_cerrada': True})
        if 'requiere_seguimiento_televentas' in vals or 'proxima_accion_id' in vals:
            self.filtered('requiere_seguimiento_televentas') \
                ._sng_crear_seguimiento_pendiente()
        return res

    def action_sng_ver_seguimientos(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'sng_control_visitas.action_sng_televentas_seguimiento')
        action['domain'] = [('visita_id', '=', self.id)]
        action['context'] = {
            'default_partner_id': self.partner_id.id,
            'default_visita_id': self.id,
            'default_origen': 'solicitud_agente',
        }
        return action

    def action_sng_cerrar_accion(self):
        self.write({'accion_cerrada': True})
