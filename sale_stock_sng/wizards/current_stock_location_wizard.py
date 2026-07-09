# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models


class CurrentStockLocationWizardLine(models.TransientModel):
    _name = "current.stock.location.wizard.line"
    _description = "Linea Reporte Existencias Actuales por Ubicacion"
    _order = "partner_id, location_id, product_id"

    wizard_id = fields.Many2one(
        "current.stock.location.wizard",
        string="Wizard",
        ondelete="cascade",
        readonly=True,
    )
    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    client_code = fields.Char(string="Codigo de cliente", readonly=True)
    location_id = fields.Many2one("stock.location", string="Ubicacion / bodega cliente", readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    product_code = fields.Char(string="Codigo producto", readonly=True)
    quantity = fields.Float(string="Cantidad actual", digits=(16, 2), readonly=True)
    reserved_quantity = fields.Float(string="Cantidad reservada", digits=(16, 2), readonly=True)
    available_quantity = fields.Float(string="Cantidad disponible", digits=(16, 2), readonly=True)
    sale_price = fields.Float(string="Precio Venta unitario", digits=(16, 2), readonly=True)
    total_value = fields.Float(string="Valor total", digits=(16, 2), readonly=True)
    salesperson_name = fields.Char(string="Vendedor", readonly=True)
    route_name = fields.Char(string="Ruta", readonly=True)

    def action_download_report(self):
        wizard = self.mapped("wizard_id")[:1]
        return wizard.action_print()

    def action_open_filters(self):
        wizard = self.mapped("wizard_id")[:1]
        return wizard.action_open_wizard()


class CurrentStockLocationWizard(models.TransientModel):
    _name = "current.stock.location.wizard"
    _description = "Wizard Reporte Existencias Actuales por Ubicacion"

    partner_ids = fields.Many2many(
        "res.partner",
        string="Clientes",
        domain=[("customer_rank", ">", 0), ("sale_location_id", "!=", False)],
    )
    user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        help="Filtra clientes por vendedor asignado.",
    )
    location_ids = fields.Many2many(
        "stock.location",
        string="Bodegas cliente",
        domain=[("usage", "=", "internal")],
        help="Si no seleccionas ninguna, se incluyen todas las bodegas de clientes.",
    )
    product_ids = fields.Many2many(
        "product.product",
        string="Productos",
    )
    only_positive = fields.Boolean(
        string="Solo existencias positivas",
        default=True,
    )
    line_ids = fields.One2many(
        "current.stock.location.wizard.line",
        "wizard_id",
        string="Resultados",
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if self.env.context.get("active_model") != "res.partner":
            return values

        partner_ids = self.env.context.get("active_ids") or [self.env.context.get("active_id")]
        partners = self.env["res.partner"].browse([pid for pid in partner_ids if pid]).exists()
        if not partners:
            return values

        locations = partners.mapped("sale_location_id")
        if "partner_ids" in fields_list:
            values["partner_ids"] = [(6, 0, partners.ids)]
        if "location_ids" in fields_list:
            values["location_ids"] = [(6, 0, locations.ids)]
        return values

    @api.onchange("user_id")
    def _onchange_user_id_fill_partners_locations(self):
        if not self.user_id:
            return

        partner_domain = [
            ("customer_rank", ">", 0),
            ("active", "=", True),
            ("sale_location_id", "!=", False),
        ]
        if "assigned_salesperson_id" in self.env["res.partner"]._fields and self.user_id.partner_id:
            partner_domain += [
                "|",
                ("user_id", "=", self.user_id.id),
                ("assigned_salesperson_id", "=", self.user_id.partner_id.id),
            ]
        else:
            partner_domain.append(("user_id", "=", self.user_id.id))

        partners = self.env["res.partner"].search(partner_domain)
        self.partner_ids = [(6, 0, partners.ids)]
        self.location_ids = [(6, 0, partners.mapped("sale_location_id").ids)]

    @api.onchange("partner_ids")
    def _onchange_partner_ids_fill_locations(self):
        if not self.partner_ids:
            return

        locations = self.partner_ids.mapped("sale_location_id")
        self.location_ids = [(6, 0, locations.ids)]

        users = self.partner_ids.mapped("user_id")
        self.user_id = users[0] if len(users) == 1 else False

    def action_print(self):
        return self.env.ref(
            "sale_stock_sng.current_stock_location_report_xlsx_action"
        ).report_action(self)

    def action_open_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Existencias Actuales por Ubicacion",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_view_results(self):
        self.ensure_one()
        line_commands = [(5, 0, 0)]
        for row in self._get_report_rows():
            line_commands.append((0, 0, {
                "partner_id": row["partner"].id,
                "client_code": row["client_code"],
                "location_id": row["location"].id,
                "product_id": row["product"].id,
                "product_code": row["product_code"],
                "quantity": row["quantity"],
                "reserved_quantity": row["reserved"],
                "available_quantity": row["available"],
                "sale_price": row["sale_price"],
                "total_value": row["total_value"],
                "salesperson_name": row["salesperson_name"],
                "route_name": row["route_name"],
            }))
        self.write({"line_ids": line_commands})

        return {
            "type": "ir.actions.act_window",
            "name": "Existencias Actuales por Ubicacion",
            "res_model": "current.stock.location.wizard.line",
            "view_mode": "list,pivot,form",
            "views": [
                (self.env.ref("sale_stock_sng.view_current_stock_location_line_list").id, "list"),
                (self.env.ref("sale_stock_sng.view_current_stock_location_line_pivot").id, "pivot"),
                (self.env.ref("sale_stock_sng.view_current_stock_location_line_form").id, "form"),
            ],
            "search_view_id": self.env.ref("sale_stock_sng.view_current_stock_location_line_search").id,
            "domain": [("wizard_id", "=", self.id)],
            "context": {
                "current_stock_location_wizard_id": self.id,
                "search_default_group_partner": 1,
                "pivot_measures": ["quantity", "reserved_quantity", "available_quantity", "total_value"],
            },
            "target": "current",
        }

    def _company_domain(self, include_false=False):
        """
        Dominio para restringir registros a las compañías permitidas
        (selector multicompañía). include_false agrega los registros
        compartidos (company_id vacío), como res.partner.
        """
        company_ids = self.env.companies.ids
        if include_false:
            return ["|", ("company_id", "=", False), ("company_id", "in", company_ids)]
        return [("company_id", "in", company_ids)]

    def _get_partners(self):
        Partner = self.env["res.partner"]
        domain = [
            ("customer_rank", ">", 0),
            ("active", "=", True),
            ("sale_location_id", "!=", False),
        ]
        if self.partner_ids:
            domain.append(("id", "in", self.partner_ids.ids))
        if self.user_id:
            if "assigned_salesperson_id" in Partner._fields and self.user_id.partner_id:
                domain += [
                    "|",
                    ("user_id", "=", self.user_id.id),
                    ("assigned_salesperson_id", "=", self.user_id.partner_id.id),
                ]
            else:
                domain.append(("user_id", "=", self.user_id.id))
        if self.location_ids:
            domain.append(("sale_location_id", "in", self.location_ids.ids))
        domain += self._company_domain(include_false=True)
        return Partner.sudo().search(domain, order="name, id")

    def _get_quant_domain(self, location):
        domain = [
            ("location_id", "child_of", location.id),
            ("product_id", "!=", False),
        ]
        if self.product_ids:
            domain.append(("product_id", "in", self.product_ids.ids))
        if self.only_positive:
            domain.append(("quantity", ">", 0))
        domain += self._company_domain()
        return domain

    def _get_product_totals(self, location):
        totals = defaultdict(lambda: {
            "product": self.env["product.product"],
            "quantity": 0.0,
            "reserved": 0.0,
            "available": 0.0,
        })
        quants = self.env["stock.quant"].sudo().with_context(active_test=False).search(
            self._get_quant_domain(location)
        )
        for quant in quants:
            product = quant.product_id
            reserved = quant.reserved_quantity if "reserved_quantity" in quant._fields else 0.0
            totals[product.id]["product"] = product
            totals[product.id]["quantity"] += quant.quantity or 0.0
            totals[product.id]["reserved"] += reserved or 0.0
            totals[product.id]["available"] += (
                quant.available_quantity
                if "available_quantity" in quant._fields
                else (quant.quantity or 0.0) - (reserved or 0.0)
            )
        return totals

    def _partner_candidates(self, partner):
        candidates = partner
        if partner.commercial_partner_id and partner.commercial_partner_id != partner:
            candidates |= partner.commercial_partner_id
        if partner.parent_id and partner.parent_id not in candidates:
            candidates |= partner.parent_id
        return candidates

    def _get_partner_salesperson_name(self, partner):
        for candidate in self._partner_candidates(partner):
            if "assigned_salesperson_id" in candidate._fields and candidate.assigned_salesperson_id:
                return candidate.assigned_salesperson_id.display_name or candidate.assigned_salesperson_id.name or ""
            if "user_id" in candidate._fields and candidate.user_id:
                return candidate.user_id.display_name or candidate.user_id.name or ""
        return ""

    def _get_partner_route_name(self, partner):
        for candidate in self._partner_candidates(partner):
            if "sales_route_id" in candidate._fields and candidate.sales_route_id:
                return candidate.sales_route_id.display_name or candidate.sales_route_id.name or ""
            if "team_id" in candidate._fields and candidate.team_id:
                return candidate.team_id.display_name or candidate.team_id.name or ""
        return ""

    def _get_partner_code(self, partner):
        return (
            getattr(partner, "client_code", False)
            or getattr(partner, "unique_id", False)
            or partner.vat
            or str(partner.id)
        )

    def _get_report_rows(self):
        self.ensure_one()
        rows = []
        for partner in self._get_partners():
            location = partner.sale_location_id
            if not location:
                continue

            product_totals = self._get_product_totals(location)
            for totals in sorted(
                product_totals.values(),
                key=lambda item: (
                    item["product"].default_code or "",
                    item["product"].display_name or "",
                ),
            ):
                product = totals["product"]
                quantity = totals["quantity"]
                if self.only_positive and quantity <= 0:
                    continue

                sale_price = product.lst_price or 0.0
                rows.append({
                    "partner": partner,
                    "client_code": self._get_partner_code(partner),
                    "location": location,
                    "product": product,
                    "product_code": product.default_code or "",
                    "quantity": quantity,
                    "reserved": totals["reserved"],
                    "available": totals["available"],
                    "sale_price": sale_price,
                    "total_value": quantity * sale_price,
                    "salesperson_name": self._get_partner_salesperson_name(partner),
                    "route_name": self._get_partner_route_name(partner),
                })
        return rows
