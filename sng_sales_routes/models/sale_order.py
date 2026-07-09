# -*- coding: utf-8 -*-

from odoo import api, fields, models


SNG_SALE_ORDER_PARTNER_ALIAS_PARAM = "sng_sales_routes.sale_order_partner_aliases"
SNG_SALE_ORDER_PARTNER_ALIAS_DEFAULT = "872:871"
SNG_SALE_ORDER_PARTNER_FIELDS = (
    "partner_id",
    "partner_invoice_id",
    "partner_shipping_id",
)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sales_route_id = fields.Many2one(
        "sng.sales.route",
        string="Ruta/Territorio",
        domain="[('active', '=', True)]",
        check_company=False,
        copy=True,
        index=True,
        help="Copia histórica de la ruta del cliente para reportes comerciales.",
    )

    @api.onchange("partner_id")
    def _onchange_partner_id_sales_route(self):
        for order in self:
            order.sales_route_id = order.partner_id.sales_route_id

    @api.model
    def _sng_sale_order_partner_aliases(self):
        alias_text = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                SNG_SALE_ORDER_PARTNER_ALIAS_PARAM,
                SNG_SALE_ORDER_PARTNER_ALIAS_DEFAULT,
            )
            or ""
        )
        aliases = {}
        for item in alias_text.replace("\n", ",").split(","):
            item = item.strip()
            if not item:
                continue
            separator = ":" if ":" in item else "="
            source, separator, target = item.partition(separator)
            if not separator:
                continue
            try:
                aliases[int(source.strip())] = int(target.strip())
            except ValueError:
                continue
        return aliases

    @api.model
    def _sng_normalize_sale_order_partner_vals(self, vals):
        aliases = self._sng_sale_order_partner_aliases()
        if not aliases:
            return vals

        for field_name in SNG_SALE_ORDER_PARTNER_FIELDS:
            partner_id = vals.get(field_name)
            if not partner_id:
                continue
            try:
                normalized_partner_id = aliases.get(int(partner_id))
            except (TypeError, ValueError):
                continue
            if normalized_partner_id:
                vals[field_name] = normalized_partner_id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sng_normalize_sale_order_partner_vals(vals)
            if vals.get("partner_id") and "sales_route_id" not in vals:
                partner = self.env["res.partner"].browse(vals["partner_id"])
                vals["sales_route_id"] = partner.sales_route_id.id or False
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._sng_normalize_sale_order_partner_vals(vals)
        if "partner_id" in vals and "sales_route_id" not in vals:
            partner = self.env["res.partner"].browse(vals["partner_id"])
            vals = dict(vals, sales_route_id=partner.sales_route_id.id or False)
        return super().write(vals)

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.sales_route_id:
            vals["sales_route_id"] = self.sales_route_id.id
        return vals
