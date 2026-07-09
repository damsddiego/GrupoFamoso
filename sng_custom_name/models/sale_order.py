from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_commercial_name = fields.Char(
        string='Nombre Comercial',
        related='partner_id.commercial_name',
        store=True,
        readonly=True,
        search='_search_partner_commercial_name',
    )

    def _search_partner_commercial_name(self, operator, value):
        return [('partner_id.commercial_name', operator, value)]

    @property
    def _rec_names_search(self):
        # Extender la búsqueda para incluir el nombre comercial del partner
        fields_list = super()._rec_names_search
        if 'partner_id.commercial_name' not in fields_list:
            fields_list = list(fields_list) + ['partner_id.commercial_name']
        return fields_list
