from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    block_sale_without_stock = fields.Boolean(
        related='company_id.block_sale_without_stock',
        readonly=False,
    )
    stock_block_allow_exception_group = fields.Boolean(
        related='company_id.stock_block_allow_exception_group',
        readonly=False,
    )
    stock_block_warehouse_ids = fields.Many2many(
        related='company_id.stock_block_warehouse_ids',
        readonly=False,
    )
