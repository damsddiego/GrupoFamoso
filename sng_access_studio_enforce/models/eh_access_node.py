# -*- coding: utf-8 -*-
from odoo import fields, models


class EhAccessNode(models.Model):
    _inherit = "eh.access.node"

    enforce_server = fields.Boolean(
        string="Bloquear también en servidor",
        help=(
            "Además de ocultar el botón, rechaza la llamada al método del"
            " mismo nombre en el servidor (RPC/API, otras vistas, código)."
            " Solo aplica a reglas de tipo Botón y solo a los métodos que"
            " tengan el gancho instalado (hoy: sale.order.action_confirm)."
        ),
    )
