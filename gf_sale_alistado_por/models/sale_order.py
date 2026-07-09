from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_gf_alistado_por = fields.Many2one(
        comodel_name='res.users',
        string='Alistado por',
        help='Usuario que realizó el alistado del pedido.',
        tracking=True,
    )
