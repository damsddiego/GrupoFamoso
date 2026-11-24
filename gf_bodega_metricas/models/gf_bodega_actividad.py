from odoo import fields, models


class GfBodegaActividad(models.Model):
    _name = 'gf.bodega.actividad'
    _description = 'Actividad de bodega'
    _order = 'sequence, id'

    name = fields.Char(string='Actividad', required=True, translate=False)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activa', default=True)
