from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    atado = fields.Char(
        string='Atado',
        help='Información de empaque o agrupación'
    )
    caja = fields.Char(
        string='Caja',
        help='Número o referencia de caja'
    )
    paquete = fields.Char(
        string='Paquete',
        help='Información del paquete de envío'
    )
