from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    header_note = fields.Html(string='Notas del Vendedor')
