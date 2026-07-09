# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    sales_route_id = fields.Many2one(
        "sng.sales.route",
        string="Ruta/Territorio",
        index=True,
        help="Clasificación comercial del cliente. No cambia el vendedor asignado.",
    )
