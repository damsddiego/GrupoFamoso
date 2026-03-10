from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    block_sale_without_stock = fields.Boolean(
        string='Block sales without stock',
        default=False,
    )
    stock_block_allow_exception_group = fields.Boolean(
        string='Allow user exceptions',
        default=False,
    )
    stock_block_warehouse_ids = fields.Many2many(
        comodel_name='stock.warehouse',
        relation='res_company_stock_block_warehouse_rel',
        column1='company_id',
        column2='warehouse_id',
        string='Warehouses to validate',
    )
