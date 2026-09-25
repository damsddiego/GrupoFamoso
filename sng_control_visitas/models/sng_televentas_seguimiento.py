# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

RESULTADOS_TELEVENTAS = [
    ('venta_recuperada', 'Venta recuperada'),
    ('pedido_pendiente', 'Pedido pendiente'),
    ('cotizacion_enviada', 'Cotización enviada'),
    ('sin_interes', 'Sin interés'),
    ('no_respondio', 'No respondió'),
    ('reprogramar_llamada', 'Reprogramar llamada'),
    ('cliente_cerrado', 'Cliente cerrado'),
    ('datos_incorrectos', 'Datos incorrectos'),
    ('bloqueado_cobro', 'Bloqueado por cobro'),
    ('inventario_suficiente', 'Inventario suficiente'),
]

EFECTIVIDAD_TELEVENTAS = {
    'venta_recuperada': 1.0,
    'pedido_pendiente': 0.5,
    'cotizacion_enviada': 0.5,
}

CANALES = [
    ('llamada', 'Llamada'),
    ('whatsapp', 'WhatsApp'),
    ('correo', 'Correo'),
    ('videollamada', 'Videollamada'),
]

ORIGENES = [
    ('no_visitado', 'Cliente no visitado'),
    ('visita_pendiente', 'Visita pendiente según frecuencia'),
    ('solicitud_agente', 'Solicitud del agente'),
    ('frecuencia_televentas', 'Frecuencia de televentas'),
    ('manual', 'Manual'),
]


class SngTeleventasSeguimiento(models.Model):
    """Gestión de televentas sobre un cliente en una semana concreta.

    Se crea pendiente (por el cron semanal, por una visita que lo pide o a
    mano) y la responsable lo cierra registrando canal, resultado, monto,
    próxima acción y comentario. Cada pendiente lleva una actividad de Odoo
    para que aparezca en la bandeja de la responsable.
    """

    _name = 'sng.televentas.seguimiento'
    _description = 'Seguimiento de televentas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha_limite, id desc'

    _SEMANA = timedelta(days=7)

    name = fields.Char(
        string='Referencia', compute='_compute_name', store=True)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, index=True,
        domain="[('customer_rank', '>', 0)]")
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda')
    visita_id = fields.Many2one(
        'sng.ruteros.visita', string='Visita de origen', index=True,
        ondelete='set null')
    vendedor_id = fields.Many2one(
        'res.partner', string='Agente asignado',
        compute='_compute_vendedor_id', store=True, index=True)
    sales_route_id = fields.Many2one(
        related='partner_id.sales_route_id', string='Ruta', store=True)
    origen = fields.Selection(
        ORIGENES, string='Origen', default='manual', required=True)
    semana = fields.Date(
        string='Semana', required=True, index=True,
        default=lambda self: self._sng_lunes(fields.Date.context_today(self)),
        help='Lunes de la semana en que debe gestionarse.')
    fecha_limite = fields.Date(
        string='Fecha límite', compute='_compute_fecha_limite', store=True)
    responsable_id = fields.Many2one(
        'res.users', string='Responsable', tracking=True, index=True,
        default=lambda self: self.env.company.sng_televentas_user_id)
    estado = fields.Selection(
        [('pendiente', 'Pendiente'),
         ('realizado', 'Realizado'),
         ('cancelado', 'Cancelado')],
        string='Estado', default='pendiente', required=True, tracking=True,
        index=True)

    fecha_seguimiento = fields.Date(string='Fecha de contacto')
    canal = fields.Selection(CANALES, string='Canal de contacto')
    resultado = fields.Selection(
        RESULTADOS_TELEVENTAS, string='Resultado televentas', tracking=True)
    monto_venta = fields.Monetary(
        string='Monto venta televentas', currency_field='currency_id')
    sale_order_id = fields.Many2one(
        'sale.order', string='Orden de venta', check_company=True)
    proxima_accion_id = fields.Many2one(
        'sng.visita.catalogo', string='Próxima acción',
        domain="[('tipo', '=', 'proxima_accion')]", ondelete='restrict')
    fecha_proxima_accion = fields.Date(string='Fecha próxima acción')
    comentario_tipo_id = fields.Many2one(
        'sng.visita.catalogo', string='Comentario predeterminado',
        domain="[('tipo', '=', 'comentario_televentas')]",
        ondelete='restrict')
    comentario = fields.Text(string='Comentario')
    accion_cerrada = fields.Boolean(string='Acción cerrada', default=False)
    efectividad = fields.Float(
        string='Efectividad televentas', compute='_compute_efectividad',
        store=True, digits=(3, 2))
    sin_comentario = fields.Boolean(
        string='Sin comentario', compute='_compute_sin_comentario',
        store=True)
    vencido = fields.Boolean(
        string='Vencido', compute='_compute_vencido', search='_search_vencido')

    # ----------------------------------------------------------------- computes

    @api.depends('partner_id', 'partner_id.commercial_name', 'semana')
    def _compute_name(self):
        for rec in self:
            cliente = (rec.partner_id.commercial_name
                       or rec.partner_id.display_name or '')
            rec.name = _('Seg. %(semana)s — %(cliente)s',
                         semana=rec.semana.strftime('%d/%m') if rec.semana else '',
                         cliente=cliente)

    @api.depends('partner_id.assigned_salesperson_id', 'company_id')
    def _compute_vendedor_id(self):
        # assigned_salesperson_id es por compañía en Grupo Famoso.
        for rec in self:
            partner = rec.partner_id
            if rec.company_id:
                partner = partner.with_company(rec.company_id)
            rec.vendedor_id = partner.assigned_salesperson_id

    @api.depends('semana')
    def _compute_fecha_limite(self):
        for rec in self:
            rec.fecha_limite = (
                rec.semana + timedelta(days=6) if rec.semana else False)

    @api.depends('resultado', 'estado')
    def _compute_efectividad(self):
        for rec in self:
            rec.efectividad = (
                EFECTIVIDAD_TELEVENTAS.get(rec.resultado, 0.0)
                if rec.estado == 'realizado' else 0.0)

    @api.depends('estado', 'comentario_tipo_id', 'comentario')
    def _compute_sin_comentario(self):
        for rec in self:
            rec.sin_comentario = bool(
                rec.estado == 'realizado'
                and not rec.comentario_tipo_id
                and not (rec.comentario or '').strip())

    @api.depends('estado', 'fecha_limite', 'fecha_proxima_accion')
    def _compute_vencido(self):
        hoy = fields.Date.context_today(self)
        for rec in self:
            limite = rec._sng_fecha_control()
            rec.vencido = bool(
                rec.estado == 'pendiente' and limite and limite < hoy)

    def _search_vencido(self, operator, value):
        hoy = fields.Date.context_today(self)
        dominio = [('estado', '=', 'pendiente'), '|',
                   '&', ('fecha_proxima_accion', '!=', False),
                   ('fecha_proxima_accion', '<', hoy),
                   '&', ('fecha_proxima_accion', '=', False),
                   ('fecha_limite', '<', hoy)]
        positivo = (operator == '=' and value) or (operator == '!=' and not value)
        return dominio if positivo else ['!'] + dominio

    # -------------------------------------------------------------- restricciones

    @api.constrains('estado', 'fecha_seguimiento', 'canal', 'resultado',
                    'comentario_tipo_id', 'comentario')
    def _check_realizado_completo(self):
        for rec in self.filtered(lambda r: r.estado == 'realizado'):
            faltan = []
            if not rec.fecha_seguimiento:
                faltan.append(_('fecha de contacto'))
            if not rec.canal:
                faltan.append(_('canal'))
            if not rec.resultado:
                faltan.append(_('resultado'))
            if not rec.comentario_tipo_id and not (rec.comentario or '').strip():
                faltan.append(_('comentario'))
            if faltan:
                raise ValidationError(_(
                    'Para marcar el seguimiento de %(cliente)s como realizado '
                    'falta: %(campos)s. Toda llamada debe quedar registrada '
                    'con un comentario.',
                    cliente=rec.partner_id.display_name,
                    campos=', '.join(faltan)))

    @api.constrains('partner_id', 'semana', 'company_id', 'estado')
    def _check_pendiente_unico(self):
        for rec in self.filtered(lambda r: r.estado == 'pendiente'):
            otro = self.search([
                ('id', '!=', rec.id),
                ('partner_id', '=', rec.partner_id.id),
                ('company_id', '=', rec.company_id.id),
                ('semana', '=', rec.semana),
                ('estado', '=', 'pendiente'),
            ], limit=1)
            if otro:
                raise ValidationError(_(
                    'El cliente %(cliente)s ya tiene un seguimiento pendiente '
                    'para la semana del %(semana)s.',
                    cliente=rec.partner_id.display_name,
                    semana=rec.semana.strftime('%d/%m/%Y')))

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _sng_lunes(fecha):
        return fecha - timedelta(days=fecha.weekday())

    def _sng_fecha_control(self):
        """Fecha contra la que se mide el vencimiento del pendiente."""
        self.ensure_one()
        return self.fecha_proxima_accion or self.fecha_limite

    def _sng_sincronizar_actividad(self):
        """Mantiene una única actividad abierta por seguimiento pendiente."""
        tipo = self.env.ref(
            'sng_control_visitas.mail_activity_type_seguimiento_televentas',
            raise_if_not_found=False)
        for rec in self:
            abiertas = rec.activity_ids.filtered(
                lambda a: not tipo or a.activity_type_id == tipo)
            if rec.estado != 'pendiente' or not rec.responsable_id:
                abiertas.unlink()
                continue
            resumen = rec.proxima_accion_id.name or dict(
                ORIGENES).get(rec.origen) or _('Seguimiento televentas')
            vals = {
                'user_id': rec.responsable_id.id,
                'date_deadline': rec._sng_fecha_control(),
                'summary': resumen,
            }
            if abiertas:
                abiertas[0].write(vals)
                (abiertas - abiertas[0]).unlink()
            else:
                rec.activity_schedule(
                    act_type_xmlid=(
                        'sng_control_visitas.'
                        'mail_activity_type_seguimiento_televentas'),
                    note=rec.comentario or False,
                    **vals)

    def _sng_cerrar_acciones_relacionadas(self):
        """Al realizar el seguimiento se cierran la próxima acción de la
        visita de origen y las de seguimientos previos del cliente."""
        for rec in self:
            if rec.visita_id and not rec.visita_id.accion_cerrada:
                rec.visita_id.accion_cerrada = True
            previos = self.search([
                ('partner_id', '=', rec.partner_id.id),
                ('id', '!=', rec.id),
                ('estado', '=', 'realizado'),
                ('accion_cerrada', '=', False),
                ('fecha_proxima_accion', '!=', False),
            ])
            if previos:
                previos.write({'accion_cerrada': True})

    # ------------------------------------------------------------------ acciones

    def action_marcar_realizado(self):
        for rec in self:
            vals = {'estado': 'realizado'}
            if not rec.fecha_seguimiento:
                vals['fecha_seguimiento'] = fields.Date.context_today(rec)
            rec.write(vals)
        return True

    def action_cancelar(self):
        self.write({'estado': 'cancelado'})
        return True

    def action_reabrir(self):
        self.write({'estado': 'pendiente'})
        return True

    # --------------------------------------------------------------------- ORM

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('semana'):
                vals['semana'] = self._sng_lunes(
                    fields.Date.to_date(vals['semana']))
            if not vals.get('responsable_id'):
                company = self.env['res.company'].browse(
                    vals.get('company_id')) or self.env.company
                if company.sng_televentas_user_id:
                    vals['responsable_id'] = company.sng_televentas_user_id.id
        recs = super().create(vals_list)
        recs._sng_sincronizar_actividad()
        return recs

    def write(self, vals):
        if vals.get('semana'):
            vals['semana'] = self._sng_lunes(fields.Date.to_date(vals['semana']))
        res = super().write(vals)
        if any(k in vals for k in ('estado', 'responsable_id', 'semana',
                                   'fecha_proxima_accion', 'proxima_accion_id')):
            self._sng_sincronizar_actividad()
        if vals.get('estado') == 'realizado':
            realizados = self.filtered(lambda r: r.estado == 'realizado')
            realizados._sng_cerrar_acciones_relacionadas()
            realizados._sng_reprogramar()
        return res

    def _sng_reprogramar(self):
        """'Reprogramar llamada' con fecha genera el siguiente pendiente."""
        for rec in self:
            if (rec.resultado != 'reprogramar_llamada'
                    or not rec.fecha_proxima_accion):
                continue
            abierto = self.search([
                ('partner_id', '=', rec.partner_id.id),
                ('company_id', '=', rec.company_id.id),
                ('estado', '=', 'pendiente'),
            ], limit=1)
            if abierto:
                continue
            self.create({
                'partner_id': rec.partner_id.id,
                'company_id': rec.company_id.id,
                'visita_id': rec.visita_id.id,
                'origen': 'manual',
                'semana': rec.fecha_proxima_accion,
                'fecha_proxima_accion': rec.fecha_proxima_accion,
                'responsable_id': rec.responsable_id.id,
                'proxima_accion_id': rec.proxima_accion_id.id,
            })
