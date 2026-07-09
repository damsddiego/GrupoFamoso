# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.onchange('type')
    def _onchange_type_set_is_storable(self):
        """Cuando el usuario cambie el tipo a 'consu' en el formulario,
        marcar automáticamente is_storable."""
        for rec in self:
            if rec.type == 'consu':
                rec.is_storable = True

