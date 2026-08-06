# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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
    vendedor_app_id = fields.Integer(
        string='ID vendedor app (sin resolver)',
        copy=False,
        help='ID de contacto que mandó la app y no existe en esta base. '
             'Se limpia cuando se asigna el vendedor real.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        index=True,
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
        check_company=True,
        help='Orden creada durante la visita (si aplica).',
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Pago',
        check_company=True,
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

    @api.constrains('vendedor_id')
    def _check_vendedor_es_vendedor(self):
        """El dominio del campo solo aplica en la interfaz; la app escribe por
        RPC y podría mandar cualquier contacto (incluso el propio cliente)."""
        for rec in self:
            if rec.vendedor_id and not rec.vendedor_id.is_salesperson:
                raise ValidationError(_(
                    'El contacto %(nombre)s no está marcado como vendedor '
                    '(is_salesperson), no puede registrarse como vendedor de '
                    'la visita.', nombre=rec.vendedor_id.display_name))

    @api.model
    def _sng_sanear_vendedor(self, vals_list):
        """Resuelve el ID de vendedor que manda la app contra esta base.

        Usa la misma resolución que los recibos de ruteros
        (`res.partner._sng_resolver_vendedor_app`, con el parámetro de sistema
        `sng_ruteros_pagos.vendedor_equivalencias`). Sin equivalencia la visita
        entra sin vendedor, guardando el ID original en `vendedor_app_id`.
        Devuelve [(índice en vals_list, aviso para el chatter)].
        """
        avisos = []
        Partner = self.env['res.partner']
        for indice, vals in enumerate(vals_list):
            if not vals.get('vendedor_id'):
                continue
            original = vals['vendedor_id']
            resuelto, aviso = Partner._sng_resolver_vendedor_app(original)
            if not aviso:
                continue
            vals['vendedor_id'] = resuelto
            if not resuelto:
                vals['vendedor_app_id'] = original
            avisos.append((indice, aviso))
        return avisos

    @api.model
    def _sng_completar_vendedor(self, vals_list):
        """Deduce el vendedor cuando la app no lo manda (o no se pudo resolver).

        Primero la orden de venta de la visita, que sales_commission_omax ya
        calculó; si no hay, el vendedor asignado al cliente. Ese campo es
        `company_dependent`, así que se lee con la compañía de la visita.
        """
        # sudo: la app se conecta con un usuario interno que no tiene por qué
        # tener permisos de ventas; solo se lee el vendedor de la orden.
        SaleOrder = self.env['sale.order'].sudo()
        Partner = self.env['res.partner']
        for vals in vals_list:
            if vals.get('vendedor_id'):
                continue
            # exists(): la app puede mandar IDs de otro entorno; leerlos sin
            # comprobar rompería con MissingError.
            vendedor = SaleOrder.browse(
                vals.get('sale_order_id')).exists().salesperson_id
            if not vendedor:
                compania = self.env['res.company'].browse(
                    vals.get('company_id')).exists() or self.env.company
                cliente = Partner.browse(vals.get('partner_id')).exists()
                vendedor = cliente.with_company(
                    compania).assigned_salesperson_id
            if vendedor and vendedor.is_salesperson:
                vals['vendedor_id'] = vendedor.id

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
                # sudo: el uuid es único a nivel global (lo genera la tableta).
                # La búsqueda debe ignorar la regla multi-compañía, si no un
                # reintento hecho desde otra compañía crearía un duplicado.
                existente = self.sudo().search(
                    [('sng_uuid', '=', uuid)], limit=1)
            if existente:
                _logger.info(
                    'sng.ruteros.visita: reintento con uuid %s, se retorna '
                    'la visita existente id=%s', uuid, existente.id)
                resultado_ids.append((pos, existente.id))
            else:
                vals_a_crear.append((pos, vals))

        # Antes del INSERT: la app manda el ID del contacto vendedor tal como
        # lo conoce ella, que puede venir de otro entorno. Sin saneo la visita
        # viola la FK y se pierde justo la evidencia GPS del cobro que sí entró.
        nuevos_vals = [v for _, v in vals_a_crear]
        avisos = self._sng_sanear_vendedor(nuevos_vals)
        self._sng_completar_vendedor(nuevos_vals)

        nuevos = super().create(nuevos_vals)
        for indice, aviso in avisos:
            nuevos[indice].message_post(body=aviso)
        for (pos, _vals), rec in zip(vals_a_crear, nuevos):
            resultado_ids.append((pos, rec.id))

        resultado_ids.sort(key=lambda t: t[0])
        return self.browse([rid for _, rid in resultado_ids])
