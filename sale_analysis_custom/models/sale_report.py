# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    # Add new field for salesperson partner (contact with is_salesperson = True)
    salesperson_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Vendedor (Contacto)",
        readonly=True,
        help="Salesperson from sales_commission_omax module (assigned_salesperson_id)"
    )

    def _select_sale(self):
        """
        Override to add the salesperson partner field.

        This integrates with the sales_commission_omax module where:
        - Each sale.order has a salesperson_id field pointing to res.partner
        - This partner has is_salesperson = True
        - We add this as a separate field in the report
        """
        select_ = super()._select_sale()

        # Add the salesperson_id from sale.order as a new field
        # This will show the partner contact marked as salesperson
        select_ += """,
            s.salesperson_id AS salesperson_partner_id"""

        return select_

    def _group_by_sale(self):
        """
        Override to add salesperson_id to GROUP BY clause.

        Since we're using s.salesperson_id in the SELECT,
        we need to include it in the GROUP BY for proper SQL aggregation.
        """
        group_by = super()._group_by_sale()

        # Add salesperson_id to GROUP BY
        group_by += """,
            s.salesperson_id"""

        return group_by
