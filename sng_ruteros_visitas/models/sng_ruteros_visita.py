# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SngRuterosVisita(models.Model):
    """Visita de un rutero (vendedor) a un cliente, registrada desde la app.

    La app captura la posición GPS al momento de la acción (abrir cliente,
    crear venta, registrar cobro) y la sube aquí. Sirve para dejar rastro de
    las visitas que NO terminan en venta ni cobro, y como evidencia de que
    la venta/cobro se hizo en el sitio del cliente.
    """

    _name = 'sng.ruteros.visita'
    _description = 'Visita de rutero a cliente (app)'
    _order = 'fecha_inicio desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
    )
    # UUID generado por la app: clave de idempotencia (las tabletas pueden
    # reintentar el envío tras un corte de red).
    sng_uuid = fields.Char(
        string='UUID app',
        index=True,
        copy=False,
        help='Identificador único generado por la tableta. Evita duplicados '
             'si la app reintenta el envío.',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        index=True,
    )
    vendedor_id = fields.Many2one(
        'res.partner',
        string='Vendedor (app)',
        domain="[('is_salesperson', '=', True)]",
        index=True,
        help='Contacto vendedor (rutero) que hizo la visita. Mismo criterio '
             'que sng_vendedor_id en los recibos de ruteros.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )
    fecha_inicio = fields.Datetime(
        string='Inicio',
        required=True,
        default=fields.Datetime.now,
    )
    fecha_fin = fields.Datetime(string='Fin')
    duracion_min = fields.Float(
        string='Duración (min)',
        compute='_compute_duracion',
        store=True,
    )
    lat = fields.Float(string='Latitud', digits=(10, 7))
    lng = fields.Float(string='Longitud', digits=(10, 7))
    distancia_m = fields.Float(
        string='Distancia al cliente (m)',
        help='Distancia entre la posición del vendedor y la ubicación '
             'registrada del cliente al momento de la visita.',
    )
    en_sitio = fields.Boolean(
        string='En sitio',
        help='La posición del vendedor estaba dentro del umbral de cercanía '
             'de la ubicación registrada del cliente.',
    )
    resultado = fields.Selection(
        [
            ('visita', 'Solo visita'),
            ('venta', 'Venta'),
            ('cobro', 'Cobro'),
            ('venta_cobro', 'Venta y cobro'),
        ],
        string='Resultado',
        default='visita',
        required=True,
        index=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de venta',
        help='Orden creada durante la visita (si aplica).',
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Pago',
        help='Cobro registrado durante la visita (si aplica).',
    )
    observaciones = fields.Text(string='Observaciones')
    sng_from_app = fields.Boolean(string='Desde app', default=True)

    @api.depends('partner_id', 'fecha_inicio')
    def _compute_name(self):
        for rec in self:
            fecha = fields.Datetime.context_timestamp(
                rec, rec.fecha_inicio) if rec.fecha_inicio else False
            rec.name = 'Visita %s — %s' % (
                fecha.strftime('%d/%m/%Y %H:%M') if fecha else '',
                rec.partner_id.display_name or '',
            )

    @api.depends('fecha_inicio', 'fecha_fin')
    def _compute_duracion(self):
        for rec in self:
            if rec.fecha_inicio and rec.fecha_fin:
                delta = rec.fecha_fin - rec.fecha_inicio
                rec.duracion_min = round(delta.total_seconds() / 60.0, 1)
            else:
                rec.duracion_min = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        """Creación idempotente por sng_uuid: si la tableta reintenta el
        envío de una visita ya registrada, se retorna la existente en lugar
        de duplicarla."""
        vals_a_crear = []
        resultado_ids = []  # (posicion, id) para reconstruir el orden

        for pos, vals in enumerate(vals_list):
            uuid = (vals.get('sng_uuid') or '').strip()
            existente = self.browse()
            if uuid:
                existente = self.search([('sng_uuid', '=', uuid)], limit=1)
            if existente:
                _logger.info(
                    'sng.ruteros.visita: reintento con uuid %s, se retorna '
                    'la visita existente id=%s', uuid, existente.id)
                resultado_ids.append((pos, existente.id))
            else:
                vals_a_crear.append((pos, vals))

        nuevos = super().create([v for _, v in vals_a_crear])
        for (pos, _), rec in zip(vals_a_crear, nuevos):
            resultado_ids.append((pos, rec.id))

        resultado_ids.sort(key=lambda t: t[0])
        return self.browse([rid for _, rid in resultado_ids])
