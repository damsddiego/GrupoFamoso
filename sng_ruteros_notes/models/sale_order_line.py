# -*- coding: utf-8 -*-
from odoo import models, fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    sng_line_note = fields.Text(
        string='Nota de línea',
        help='Nota adicional para esta línea de venta, enviada desde la app móvil app_ruteros.',
    )
