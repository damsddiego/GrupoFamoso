# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    _CUSTOMER_ROUTE_MOVE_TYPES = ("out_invoice", "out_refund", "out_receipt")

    sales_route_id = fields.Many2one(
        "sng.sales.route",
        string="Ruta/Territorio",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
        copy=True,
        index=True,
        help="Copia histórica de la ruta del cliente u orden para reportes comerciales.",
    )

    @api.onchange("partner_id")
    def _onchange_partner_id_sales_route(self):
        for move in self:
            if move.move_type in ("out_invoice", "out_refund", "out_receipt"):
                move.sales_route_id = move.partner_id.sales_route_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "sales_route_id" in vals:
                continue
            move_type = vals.get("move_type") or self.default_get(["move_type"]).get("move_type")
            if move_type not in self._CUSTOMER_ROUTE_MOVE_TYPES:
                continue
            route_id = False
            if vals.get("reversed_entry_id"):
                route_id = self.browse(vals["reversed_entry_id"]).sales_route_id.id
            if not route_id and vals.get("partner_id"):
                route_id = self.env["res.partner"].browse(vals["partner_id"]).sales_route_id.id
            if route_id:
                vals["sales_route_id"] = route_id
        return super().create(vals_list)

    def write(self, vals):
        if "partner_id" not in vals or "sales_route_id" in vals:
            return super().write(vals)

        customer_moves = self.filtered(
            lambda move: move.move_type in self._CUSTOMER_ROUTE_MOVE_TYPES
        )
        other_moves = self - customer_moves
        res = True
        if customer_moves:
            partner = self.env["res.partner"].browse(vals["partner_id"])
            res = super(AccountMove, customer_moves).write(
                dict(vals, sales_route_id=partner.sales_route_id.id or False)
            )
        if other_moves:
            res = super(AccountMove, other_moves).write(vals) and res
        return res
