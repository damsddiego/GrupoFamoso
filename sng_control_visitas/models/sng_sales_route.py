# -*- coding: utf-8 -*-
from odoo import fields, models

TIPOS_ATENCION = [
    ('ruta', 'Ruta (visita presencial)'),
    ('televentas', 'Televentas'),
    ('oficina', 'Oficina / corporativo'),
]

FRECUENCIAS = [
    ('semanal', 'Semanal'),
    ('quincenal', 'Quincenal'),
    ('mensual', 'Mensual'),
    ('bimensual', 'Bimensual'),
    ('sin_visita', 'Sin visita programada'),
]

DIAS_FRECUENCIA = {
    'semanal': 7,
    'quincenal': 15,
    'mensual': 30,
    'bimensual': 60,
}


class SngSalesRoute(models.Model):
    _inherit = 'sng.sales.route'

    sng_tipo_atencion = fields.Selection(
        TIPOS_ATENCION,
        string='Tipo de atención',
        default='ruta',
        required=True,
        help='Define si los clientes de la ruta se visitan en sitio o se '
             'atienden por televentas / oficina. Determina qué se espera '
             'cada período en la matriz de control.',
    )
    sng_frecuencia_visita = fields.Selection(
        FRECUENCIAS,
        string='Frecuencia de visita',
        default='mensual',
        required=True,
        help='Frecuencia esperada de visita o contacto para los clientes '
             'de la ruta. Cada cliente puede tener una frecuencia propia.',
    )
