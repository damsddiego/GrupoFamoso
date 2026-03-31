from odoo import fields, models


class SngReturnReason(models.Model):
    _name = "sng.return.reason"
    _description = "Motivo de Devolucion"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Motivo", required=True, translate=True)
    active = fields.Boolean(default=True)
