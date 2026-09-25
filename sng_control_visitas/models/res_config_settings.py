# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sng_televentas_user_id = fields.Many2one(
        related='company_id.sng_televentas_user_id', readonly=False)
    sng_control_visitas_dias_alerta_factura = fields.Integer(
        related='company_id.sng_control_visitas_dias_alerta_factura',
        readonly=False)
