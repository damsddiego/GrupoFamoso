# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sng_televentas_user_id = fields.Many2one(
        'res.users',
        string='Responsable de televentas',
        help='Usuario al que se asignan por defecto los seguimientos de '
             'televentas y sus actividades.',
    )
    sng_control_visitas_dias_alerta_factura = fields.Integer(
        string='Días sin facturar para alerta',
        default=90,
        help='Umbral de la alerta gerencial "Más de N días sin facturar".',
    )
