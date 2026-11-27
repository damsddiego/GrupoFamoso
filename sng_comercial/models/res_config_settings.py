# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sng_comercial_bodega_company_id = fields.Many2one(
        related='company_id.sng_comercial_bodega_company_id', readonly=False)
