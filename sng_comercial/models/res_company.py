# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    sng_comercial_bodega_company_id = fields.Many2one(
        'res.company', string='Compañía bodega del grupo',
        help='Compañía que guarda inventario para esta. En el inventario comercial, '
             'la columna «Bodega grupo» suma el stock que esa compañía tiene del '
             'producto con la misma referencia interna.')

    @api.constrains('sng_comercial_bodega_company_id')
    def _check_sng_comercial_bodega_company(self):
        for company in self:
            if company.sng_comercial_bodega_company_id == company:
                raise ValidationError(_('La compañía bodega del grupo no puede ser la misma compañía.'))
