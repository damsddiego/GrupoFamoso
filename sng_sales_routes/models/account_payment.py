# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    sales_route_id = fields.Many2one(
        "sng.sales.route",
        string="Ruta/Territorio",
        compute="_compute_sales_route_id",
        store=True,
        readonly=False,
        index=True,
        help="Ruta inferida desde facturas conciliadas o desde el cliente.",
    )

    @api.depends(
        "partner_id",
        "invoice_ids.sales_route_id",
        "move_id.line_ids.matched_debit_ids",
        "move_id.line_ids.matched_credit_ids",
    )
    def _compute_sales_route_id(self):
        for payment in self:
            invoices = payment.reconciled_invoice_ids or payment.invoice_ids
            routes = invoices.mapped("sales_route_id").sorted(key=lambda route: route.id)

            if len(routes) == 1:
                payment.sales_route_id = routes
            elif len(routes) > 1:
                payment.sales_route_id = payment.partner_id.sales_route_id or routes[0]
            else:
                payment.sales_route_id = payment.partner_id.sales_route_id
