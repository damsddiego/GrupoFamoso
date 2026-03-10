from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    auto_discount_code_id = fields.Many2one(
        comodel_name='discount.code',
        string='Código de Descuento por Defecto',
        help='Código de descuento que se aplicará automáticamente cuando hay un descuento en la línea de factura',
        config_parameter='sng_auto_discount_fields.auto_discount_code_id'
    )

    auto_discount_note = fields.Char(
        string='Nota de Descuento por Defecto',
        help='Texto que se aplicará automáticamente en el campo "Nota de Descuento" cuando hay un descuento',
        config_parameter='sng_auto_discount_fields.auto_discount_note',
        default='Promo'
    )

    enable_auto_discount_fields = fields.Boolean(
        string='Activar Auto-llenado de Campos de Descuento',
        help='Si está activado, los campos de código y nota de descuento se llenarán automáticamente',
        config_parameter='sng_auto_discount_fields.enable_auto_discount_fields',
        default=True
    )
