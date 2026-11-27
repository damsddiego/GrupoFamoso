# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Clasificación comercial tomada de los atributos marcados con un uso en
    # product.attribute. Se almacena para que los reportes (SQL) y cualquier
    # vista puedan agrupar sin recorrer las líneas de atributo.
    sng_pilar_id = fields.Many2one(
        'product.attribute.value', string='Pilar', compute='_compute_sng_comercial',
        store=True, index=True)
    sng_base_id = fields.Many2one(
        'product.attribute.value', string='Base', compute='_compute_sng_comercial',
        store=True)
    sng_volumen_id = fields.Many2one(
        'product.attribute.value', string='Volumen', compute='_compute_sng_comercial',
        store=True)
    sng_litros_unidad = fields.Float(
        string='Litros por unidad', digits=(16, 3), compute='_compute_sng_comercial',
        store=True)

    @api.depends(
        'attribute_line_ids.active',
        'attribute_line_ids.value_ids',
        'attribute_line_ids.value_ids.sng_litros',
        'attribute_line_ids.attribute_id.sng_comercial_rol',
    )
    def _compute_sng_comercial(self):
        Value = self.env['product.attribute.value']
        for template in self:
            valores = {'pilar': Value, 'base': Value, 'volumen': Value}
            for line in template.attribute_line_ids:
                rol = line.attribute_id.sng_comercial_rol
                if rol and not valores[rol]:
                    # Con varios valores en la línea manda el primero.
                    valores[rol] = line.value_ids[:1]
            template.sng_pilar_id = valores['pilar']
            template.sng_base_id = valores['base']
            template.sng_volumen_id = valores['volumen']
            template.sng_litros_unidad = valores['volumen'].sng_litros
