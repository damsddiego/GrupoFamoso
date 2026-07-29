from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sng_lock_price_unit = fields.Boolean(
        string='Bloquear precio unitario',
        help="Impide guardar una linea de venta con un precio unitario distinto "
             "al que calcula la lista de precios del pedido.",
        default=False,
    )
    sng_lock_discount = fields.Boolean(
        string='Bloquear descuento',
        help="Impide guardar una linea de venta con un descuento distinto al que "
             "define la regla de la lista de precios. Si la regla no define "
             "descuento, el descuento debe quedar en 0.",
        default=False,
    )
    sng_price_lock_mode = fields.Selection(
        selection=[
            ('exact', 'Exactamente el precio de la lista'),
            ('no_lower', 'Permitir precios mayores, bloquear menores'),
        ],
        string='Modo de bloqueo de precio',
        default='exact',
        required=True,
    )
    sng_discount_lock_mode = fields.Selection(
        selection=[
            ('exact', 'Exactamente el descuento de la lista'),
            ('no_higher', 'Permitir descuentos menores, bloquear mayores'),
        ],
        string='Modo de bloqueo de descuento',
        default='exact',
        required=True,
    )
    sng_price_lock_tolerance = fields.Float(
        string='Tolerancia (%)',
        help="Desviacion porcentual admitida sobre el precio de la lista antes de "
             "bloquear. Dejar en 0 para exigir coincidencia exacta.",
        default=0.0,
    )
