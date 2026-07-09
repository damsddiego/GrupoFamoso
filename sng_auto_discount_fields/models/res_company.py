from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _default_auto_discount_code_id(self):
        return int(
            self.env['ir.config_parameter'].sudo().get_param(
                'sng_auto_discount_fields.auto_discount_code_id',
                0,
            ) or 0
        )

    def _default_auto_discount_note(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'sng_auto_discount_fields.auto_discount_note',
            'Promo',
        )

    def _default_enable_auto_discount_fields(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'sng_auto_discount_fields.enable_auto_discount_fields',
            'True',
        ) == 'True'

    auto_discount_code_id = fields.Many2one(
        comodel_name='discount.code',
        string='Código de Descuento por Defecto',
        help=(
            'Código de descuento que se aplicará automáticamente '
            'cuando hay un descuento en la línea de factura'
        ),
        default=_default_auto_discount_code_id,
    )
    auto_discount_note = fields.Char(
        string='Nota de Descuento por Defecto',
        help=(
            'Texto que se aplicará automáticamente en el campo '
            '"Nota de Descuento" cuando hay un descuento'
        ),
        default=_default_auto_discount_note,
    )
    enable_auto_discount_fields = fields.Boolean(
        string='Activar Auto-llenado de Campos de Descuento',
        help=(
            'Si está activado, los campos de código y nota de '
            'descuento se llenarán automáticamente'
        ),
        default=_default_enable_auto_discount_fields,
    )
