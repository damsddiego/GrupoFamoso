# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

from .sng_sales_route import DIAS_FRECUENCIA, FRECUENCIAS, TIPOS_ATENCION

RESULTADOS_NO_VISITA = ('no_visitado', 'visita_reprogramada')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sng_visita_ids = fields.One2many(
        'sng.ruteros.visita', 'partner_id', string='Visitas')
    sng_seguimiento_ids = fields.One2many(
        'sng.televentas.seguimiento', 'partner_id',
        string='Seguimientos televentas')
    sng_visita_count = fields.Integer(
        string='Visitas', compute='_compute_sng_visita_count')
    sng_seguimiento_count = fields.Integer(
        string='Seguimientos', compute='_compute_sng_visita_count')

    sng_tipo_atencion = fields.Selection(
        TIPOS_ATENCION,
        string='Tipo de atención',
        compute='_compute_sng_tipo_atencion',
        store=True,
        readonly=False,
        help='Por defecto el de la ruta. Se puede fijar por cliente.',
    )
    sng_frecuencia_visita = fields.Selection(
        FRECUENCIAS,
        string='Frecuencia de visita',
        compute='_compute_sng_frecuencia_visita',
        store=True,
        readonly=False,
        help='Por defecto la de la ruta. Se puede fijar por cliente '
             '(por ejemplo "Bimensual").',
    )
    sng_excluir_matriz = fields.Boolean(
        string='Excluir de la matriz de visitas',
        tracking=True,
        help='Clientes genéricos (tiquetes OCASIONAL, cliente ocasional '
             'público) u otros que no se atienden por ruta ni televentas: '
             'no aparecen en la matriz ni generan pendientes de televentas.',
    )
    sng_fecha_ultima_visita = fields.Date(
        string='Última visita',
        compute='_compute_sng_fechas_visita',
        store=True,
    )
    sng_fecha_proxima_visita = fields.Date(
        string='Próxima visita esperada',
        compute='_compute_sng_fechas_visita',
        store=True,
        help='Última visita real más los días de la frecuencia. Vacío si '
             'nunca se ha visitado o no aplica visita.',
    )
    sng_fecha_ultimo_contacto_televentas = fields.Date(
        string='Último contacto televentas',
        compute='_compute_sng_fecha_ultimo_contacto',
        store=True,
    )

    @api.depends('sng_visita_ids', 'sng_seguimiento_ids')
    def _compute_sng_visita_count(self):
        for partner in self:
            partner.sng_visita_count = len(partner.sng_visita_ids)
            partner.sng_seguimiento_count = len(partner.sng_seguimiento_ids)

    @api.depends('sales_route_id.sng_tipo_atencion')
    def _compute_sng_tipo_atencion(self):
        for partner in self:
            partner.sng_tipo_atencion = (
                partner.sales_route_id.sng_tipo_atencion or 'ruta')

    @api.depends('sales_route_id.sng_frecuencia_visita')
    def _compute_sng_frecuencia_visita(self):
        for partner in self:
            partner.sng_frecuencia_visita = (
                partner.sales_route_id.sng_frecuencia_visita or 'mensual')

    @api.depends('sng_visita_ids.fecha_inicio',
                 'sng_visita_ids.resultado_comercial',
                 'sng_frecuencia_visita', 'sng_tipo_atencion')
    def _compute_sng_fechas_visita(self):
        for partner in self:
            reales = partner.sng_visita_ids.filtered(
                lambda v: v.fecha_inicio
                and v.resultado_comercial not in RESULTADOS_NO_VISITA)
            ultima = max(reales.mapped('fecha_inicio'), default=False)
            partner.sng_fecha_ultima_visita = (
                fields.Datetime.context_timestamp(partner, ultima).date()
                if ultima else False)
            dias = DIAS_FRECUENCIA.get(partner.sng_frecuencia_visita)
            if (partner.sng_fecha_ultima_visita and dias
                    and partner.sng_tipo_atencion == 'ruta'):
                partner.sng_fecha_proxima_visita = (
                    partner.sng_fecha_ultima_visita + timedelta(days=dias))
            else:
                partner.sng_fecha_proxima_visita = False

    @api.depends('sng_seguimiento_ids.fecha_seguimiento',
                 'sng_seguimiento_ids.estado')
    def _compute_sng_fecha_ultimo_contacto(self):
        for partner in self:
            realizados = partner.sng_seguimiento_ids.filtered(
                lambda s: s.estado == 'realizado' and s.fecha_seguimiento)
            partner.sng_fecha_ultimo_contacto_televentas = max(
                realizados.mapped('fecha_seguimiento'), default=False)

    def action_sng_ver_visitas(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'sng_ruteros_visitas.action_sng_ruteros_visitas')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action

    def action_sng_ver_seguimientos(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'sng_control_visitas.action_sng_televentas_seguimiento')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id,
                             'search_default_partner_id': self.id}
        return action
