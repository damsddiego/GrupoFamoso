from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    auto_discount_code_id = fields.Many2one(
        related='company_id.auto_discount_code_id',
        readonly=False,
    )

    auto_discount_note = fields.Char(
        related='company_id.auto_discount_note',
        readonly=False,
    )

    enable_auto_discount_fields = fields.Boolean(
        related='company_id.enable_auto_discount_fields',
        readonly=False,
    )
