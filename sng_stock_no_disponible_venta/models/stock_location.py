# -*- coding: utf-8 -*-
from odoo import fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    # Se marcan las pocas ubicaciones que NO cuentan (dañado, desecho,
    # exhibición, marketing) y todo lo demás cuenta por defecto: así una
    # ubicación nueva nunca queda oculta por olvido.
    sng_no_disponible_venta = fields.Boolean(
        string='No disponible para venta',
        default=False,
        index=True,
        help='El stock de esta ubicación, y de todas las que cuelgan de ella, '
             'no se cuenta como disponible en las apps de SNG (escritorio y '
             'móvil). La ubicación sigue existiendo y viéndose en Odoo; solo '
             'deja de sumar al disponible que ven los vendedores. No cambia de '
             'dónde reservan las entregas.',
    )
