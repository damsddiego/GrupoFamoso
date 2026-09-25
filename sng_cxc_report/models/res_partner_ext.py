# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    sng_credit_blocked = fields.Boolean(
        string="Credito bloqueado (CxC)",
        default=False,
        tracking=True,
        help="Bloqueado desde el plan de accion CxC. Impide confirmar ordenes de venta.",
    )
