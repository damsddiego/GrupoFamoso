# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SalesCommissionAnalysis(models.Model):
    _inherit = "sales.commission.analysis"

    sales_route_id = fields.Many2one(
        "sng.sales.route",
        string="Ruta/Territorio",
        index=True,
        readonly=True,
        help="Ruta copiada desde la orden, factura o cliente relacionado.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("sales_route_id"):
                continue
            route_id = False
            if vals.get("sale_order_id"):
                route_id = self.env["sale.order"].browse(vals["sale_order_id"]).sales_route_id.id
            if not route_id and vals.get("move_id"):
                route_id = self.env["account.move"].browse(vals["move_id"]).sales_route_id.id
            if not route_id and vals.get("partner_id"):
                route_id = self.env["res.partner"].browse(vals["partner_id"]).sales_route_id.id
            if route_id:
                vals["sales_route_id"] = route_id
        return super().create(vals_list)
