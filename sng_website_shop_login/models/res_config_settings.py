from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sng_shop_login_required = fields.Boolean(
        related='website_id.sng_shop_login_required', readonly=False)
