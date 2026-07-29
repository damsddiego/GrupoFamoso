from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sng_lock_price_unit = fields.Boolean(
        related='company_id.sng_lock_price_unit',
        readonly=False,
    )
    sng_lock_discount = fields.Boolean(
        related='company_id.sng_lock_discount',
        readonly=False,
    )
    sng_price_lock_mode = fields.Selection(
        related='company_id.sng_price_lock_mode',
        readonly=False,
    )
    sng_discount_lock_mode = fields.Selection(
        related='company_id.sng_discount_lock_mode',
        readonly=False,
    )
    sng_price_lock_tolerance = fields.Float(
        related='company_id.sng_price_lock_tolerance',
        readonly=False,
    )
