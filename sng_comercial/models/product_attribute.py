# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..litros import litros_desde_texto

ROLES = [
    ('pilar', 'Pilar'),
    ('base', 'Base'),
    ('volumen', 'Volumen'),
]


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    sng_comercial_rol = fields.Selection(
        ROLES, string='Uso en reportes comerciales', copy=False, index=True,
        help='Indica a la app Comercial qué atributo clasifica los productos por '
             'pilar, por base o por volumen. Solo puede haber un atributo por uso. '
             'Los productos con valor en el atributo de pilar entran a los reportes.')

    @api.constrains('sng_comercial_rol')
    def _check_sng_comercial_rol(self):
        for attribute in self.filtered('sng_comercial_rol'):
            otro = self.with_context(active_test=False).search([
                ('sng_comercial_rol', '=', attribute.sng_comercial_rol),
                ('id', '!=', attribute.id),
            ], limit=1)
            if otro:
                raise ValidationError(_(
                    'El atributo «%(otro)s» ya está marcado como %(rol)s en los reportes '
                    'comerciales. Quítale ese uso antes de dárselo a «%(nuevo)s».',
                    otro=otro.name, nuevo=attribute.name,
                    rol=dict(ROLES)[attribute.sng_comercial_rol].lower()))

    def write(self, vals):
        res = super().write(vals)
        if vals.get('sng_comercial_rol') == 'volumen':
            # Propone los litros de los valores que aún no los tienen.
            for value in self.value_ids.filtered(lambda v: not v.sng_litros):
                value.sng_litros = litros_desde_texto(value.name)
        return res


class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    sng_litros = fields.Float(
        string='Litros por unidad', digits=(16, 3),
        help='Litros que trae una unidad del producto con este volumen '
             '(1L = 1, 400ml = 0.4, estañón = 208). Con esto la app Comercial '
             'convierte unidades a litros.')

    @api.model_create_multi
    def create(self, vals_list):
        values = super().create(vals_list)
        for value, vals in zip(values, vals_list):
            if 'sng_litros' not in vals and value.attribute_id.sng_comercial_rol == 'volumen':
                value.sng_litros = litros_desde_texto(value.name)
        return values
