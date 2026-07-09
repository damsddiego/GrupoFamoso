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
    ordered_qty = fields.Float(string="Cant. ordenada", readonly=True)
    ordered_amount = fields.Monetary(string="Monto ordenado", readonly=True)
    delivered_qty = fields.Float(string="Cant. entregada", readonly=True)
    denied_qty = fields.Float(string="Negado", readonly=True)
    denied_amount = fields.Monetary(string="Monto negado", readonly=True)
    delivered_amount = fields.Monetary(string="Monto entregado", readonly=True)
    invoiced_qty = fields.Float(string="Cant. facturada", readonly=True)
    invoiced_amount = fields.Monetary(string="Monto facturado", readonly=True)
    has_invoice = fields.Boolean(string="Tiene factura", readonly=True)

    def _select_sale(self):
        """
        Override to add the salesperson partner field.

        This integrates with the sales_commission_omax module where:
        - Each sale.order has a salesperson_id field pointing to res.partner
        - This partner has is_salesperson = True
        - We add this as a separate field in the report
        """
        select_ = super()._select_sale()

        currency_rate = self._case_value_or_one('s.currency_rate')
        company_rate = self._case_value_or_one('account_currency_table.rate')
        gross_delivered_qty = """
            COALESCE((
                SELECT SUM(sm.quantity / sm_u.factor * u.factor)
                  FROM stock_move sm
                  JOIN uom_uom sm_u ON sm_u.id = sm.product_uom
                  JOIN stock_location dest_location
                    ON dest_location.id = COALESCE(sm.location_final_id, sm.location_dest_id)
                 WHERE sm.sale_line_id = l.id
                   AND sm.state = 'done'
                   AND sm.scrapped = FALSE
                   AND sm.product_id = l.product_id
                   AND sm.origin_returned_move_id IS NULL
                   AND dest_location.usage = 'customer'
            ), 0)
        """

        # Add the salesperson_id from sale.order as a new field.
        # The extra measures are aliases/custom amounts for a focused pivot view.
        select_ += """,
            s.salesperson_id AS salesperson_partner_id,
            EXISTS (
                SELECT 1
                  FROM sale_order_line sol_invoice
                  JOIN sale_order_line_invoice_rel soli_rel
                    ON soli_rel.order_line_id = sol_invoice.id
                  JOIN account_move_line aml_invoice
                    ON aml_invoice.id = soli_rel.invoice_line_id
                  JOIN account_move am_invoice
                    ON am_invoice.id = aml_invoice.move_id
                 WHERE sol_invoice.order_id = s.id
                   AND am_invoice.move_type = 'out_invoice'
                   AND (
                       am_invoice.state != 'cancel'
                       OR am_invoice.payment_state = 'invoicing_legacy'
                   )
            ) AS has_invoice,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(l.product_uom_qty / u.factor * u2.factor) ELSE 0 END AS ordered_qty,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(l.price_subtotal
                / {currency_rate}
                * {company_rate}
                ) ELSE 0
            END AS ordered_amount,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(({gross_delivered_qty}) / u.factor * u2.factor) ELSE 0 END AS delivered_qty,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(
                (l.product_uom_qty - ({gross_delivered_qty})) / u.factor * u2.factor
            ) ELSE 0 END AS denied_qty,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(
                    CASE COALESCE(l.product_uom_qty, 0)
                        WHEN 0 THEN 0
                        ELSE l.price_subtotal * (l.product_uom_qty - ({gross_delivered_qty})) / l.product_uom_qty
                    END
                / {currency_rate}
                * {company_rate}
                ) ELSE 0
            END AS denied_amount,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(
                    CASE COALESCE(l.product_uom_qty, 0)
                        WHEN 0 THEN 0
                        ELSE l.price_subtotal * ({gross_delivered_qty}) / l.product_uom_qty
                    END
                / {currency_rate}
                * {company_rate}
                ) ELSE 0
            END AS delivered_amount,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(l.qty_invoiced / u.factor * u2.factor) ELSE 0 END AS invoiced_qty,
            CASE WHEN l.product_id IS NOT NULL OR l.is_downpayment THEN SUM(l.untaxed_amount_invoiced
                / {currency_rate}
                * {company_rate}
                ) ELSE 0
            END AS invoiced_amount""".format(
                currency_rate=currency_rate,
                company_rate=company_rate,
                gross_delivered_qty=gross_delivered_qty,
            )

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
