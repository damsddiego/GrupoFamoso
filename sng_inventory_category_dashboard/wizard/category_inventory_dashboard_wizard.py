# -*- coding: utf-8 -*-

import base64
import io
import re
from collections import defaultdict
from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

try:
    import xlsxwriter
    from xlsxwriter.utility import xl_col_to_name
except ImportError:
    xlsxwriter = None
    xl_col_to_name = None


class CategoryInventoryDashboardWizard(models.TransientModel):
    _name = "category.inventory.dashboard.wizard"
    _description = "Wizard Dashboard de Inventario por Categorias"

    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
    )
    category_ids = fields.Many2many(
        "product.category",
        string="Categorias",
        help="Si se deja vacio, se usaran las categorias raiz que tengan productos almacenables.",
    )
    include_child_categories = fields.Boolean(
        string="Incluir subcategorias",
        default=True,
    )
    date_from = fields.Date(
        string="Fecha inicial",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(month=1, day=1),
    )
    date_to = fields.Date(
        string="Fecha final",
        required=True,
        default=fields.Date.context_today,
    )
    period_mode = fields.Selection(
        [
            ("monthly", "Mensual"),
            ("weekly", "Semanal"),
            ("both", "Mensual y semanal"),
        ],
        string="Desglose",
        default="both",
        required=True,
    )
    can_view_cost = fields.Boolean(
        string="Puede ver costos",
        compute="_compute_can_view_cost",
    )
    excel_file = fields.Binary(string="Archivo Excel", readonly=True)
    excel_filename = fields.Char(string="Nombre de archivo", readonly=True)

    @api.depends_context("uid")
    def _compute_can_view_cost(self):
        has_group = self.env.user.has_group("custom_ui_security.group_view_product_cost")
        for wizard in self:
            wizard.can_view_cost = has_group

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("La fecha inicial no puede ser mayor que la fecha final."))

    def action_export_excel(self):
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(
                _("La libreria Python 'xlsxwriter' es necesaria para generar este reporte.")
            )

        snapshot = self._build_report_snapshot()
        output = self._build_excel(snapshot)
        filename = "dashboard_inventario_categorias_%s_%s.xlsx" % (
            self.date_from,
            self.date_to,
        )
        self.write(
            {
                "excel_file": base64.b64encode(output.getvalue()),
                "excel_filename": filename,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": (
                f"/web/content/{self._name}/{self.id}"
                f"/excel_file/{filename}?download=true"
            ),
            "target": "self",
        }

    def _build_report_snapshot(self, categories=None):
        self.ensure_one()
        categories = categories or self._get_report_categories()
        if not categories:
            raise UserError(
                _(
                    "No se encontraron categorias con productos almacenables para los filtros seleccionados."
                )
            )

        modes = self._get_modes()
        periods_by_mode = {mode: self._get_periods(mode) for mode in modes}
        dashboard_mode = "monthly" if "monthly" in modes else "weekly"
        categories_data = []
        can_view_cost = self.can_view_cost

        for category in categories:
            products = self._get_category_products(category)
            if not products:
                continue

            standard_prices = {
                product.id: product.with_company(self.company_id).standard_price
                for product in products
            }
            metrics_by_mode = {}
            for mode in modes:
                metrics_by_mode[mode] = self._compute_category_metrics(
                    category,
                    products,
                    periods_by_mode[mode],
                    standard_prices,
                )
            categories_data.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "display_name": category.complete_name,
                    "target_days": category.inventory_dashboard_target_days or 0.0,
                    "buy_threshold": category.inventory_dashboard_buy_threshold or 0.0,
                    "liquidate_threshold": category.inventory_dashboard_liquidate_threshold or 0.0,
                    "metrics": metrics_by_mode,
                }
            )

        if not categories_data:
            raise UserError(
                _(
                    "No se encontraron categorias con productos almacenables para los filtros seleccionados."
                )
            )

        return {
            "company": self.company_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "modes": modes,
            "dashboard_mode": dashboard_mode,
            "periods_by_mode": periods_by_mode,
            "categories": categories_data,
            "can_view_cost": can_view_cost,
        }

    def _get_report_categories(self):
        self.ensure_one()
        if self.category_ids:
            return self.category_ids.sorted(key=lambda c: c.complete_name or c.name or "")

        products = self.env["product.product"].search([("is_storable", "=", True)])
        categories = products.mapped("categ_id")
        root_categories = self.env["product.category"]
        for category in categories:
            current = category
            while current.parent_id:
                current = current.parent_id
            root_categories |= current
        return root_categories.sorted(key=lambda c: c.complete_name or c.name or "")

    def _get_modes(self):
        self.ensure_one()
        if self.period_mode == "both":
            return ["monthly", "weekly"]
        return [self.period_mode]

    def _get_category_products(self, category):
        self.ensure_one()
        category_operator = "child_of" if self.include_child_categories else "="
        return self.env["product.product"].search(
            [
                ("is_storable", "=", True),
                ("categ_id", category_operator, category.id),
            ],
            order="default_code, id",
        )

    def _get_periods(self, mode):
        self.ensure_one()
        periods = []
        current_start = self.date_from
        sequence = 1
        multiple_years = self.date_from.year != self.date_to.year

        while current_start <= self.date_to:
            if mode == "monthly":
                natural_end = current_start + relativedelta(day=31)
                end_date = min(natural_end, self.date_to)
                label = self._format_month_label(current_start, multiple_years)
            else:
                end_date = min(current_start + timedelta(days=6), self.date_to)
                label = _("Sem %(number)s") % {"number": sequence}

            periods.append(
                {
                    "index": sequence,
                    "label": label,
                    "date_from": current_start,
                    "date_to": end_date,
                    "days": (end_date - current_start).days + 1,
                }
            )
            current_start = end_date + timedelta(days=1)
            sequence += 1

        return periods

    def _format_month_label(self, date_value, multiple_years=False):
        months = {
            1: _("Ene"),
            2: _("Feb"),
            3: _("Mar"),
            4: _("Abr"),
            5: _("May"),
            6: _("Jun"),
            7: _("Jul"),
            8: _("Ago"),
            9: _("Sep"),
            10: _("Oct"),
            11: _("Nov"),
            12: _("Dic"),
        }
        label = months[date_value.month]
        if multiple_years:
            label = "%s %s" % (label, date_value.year)
        return label

    def _compute_category_metrics(self, category, products, periods, standard_prices):
        metrics = []
        for period in periods:
            start_dt = datetime.combine(period["date_from"], time.min)
            end_dt = datetime.combine(period["date_to"], time.max)
            opening_dt = start_dt - timedelta(seconds=1)

            opening_qty_map = self._get_qty_map(products, opening_dt)
            closing_qty_map = self._get_qty_map(products, end_dt)
            incoming_qty_map = self._get_move_qty_map(
                products,
                start_dt,
                end_dt,
                ("location_id.usage", "!=", "internal"),
                ("location_dest_id.usage", "=", "internal"),
            )
            sales_qty_map = self._get_move_qty_map(
                products,
                start_dt,
                end_dt,
                ("location_id.usage", "=", "internal"),
                ("location_dest_id.usage", "=", "customer"),
            )

            opening_qty = sum(opening_qty_map.values())
            incoming_qty = sum(incoming_qty_map.values())
            sales_qty = sum(sales_qty_map.values())
            closing_qty = sum(closing_qty_map.values())
            avg_daily_qty = sales_qty / period["days"] if period["days"] else 0.0
            days_inventory = closing_qty / avg_daily_qty if avg_daily_qty else 0.0

            inventory_value = sum(
                closing_qty_map[product_id] * standard_prices.get(product_id, 0.0)
                for product_id in closing_qty_map
            )
            sales_value = sum(
                sales_qty_map[product_id] * standard_prices.get(product_id, 0.0)
                for product_id in sales_qty_map
            )
            average_price = 0.0
            if closing_qty:
                average_price = inventory_value / closing_qty
            elif sales_qty:
                average_price = sales_value / sales_qty

            target_days = category.inventory_dashboard_target_days or 0.0
            suggested_purchase = max(0.0, (target_days * avg_daily_qty) - closing_qty)
            action = self._get_action_label(
                days_inventory,
                category.inventory_dashboard_buy_threshold or 0.0,
                category.inventory_dashboard_liquidate_threshold or 0.0,
            )

            metrics.append(
                {
                    "opening_qty": opening_qty,
                    "incoming_qty": incoming_qty,
                    "sales_qty": sales_qty,
                    "closing_qty": closing_qty,
                    "avg_daily_qty": avg_daily_qty,
                    "days_inventory": days_inventory,
                    "average_price": average_price,
                    "sales_value": sales_value,
                    "inventory_value": inventory_value,
                    "target_days": target_days,
                    "suggested_purchase": suggested_purchase,
                    "action": action,
                }
            )
        return metrics

    def _get_qty_map(self, products, date_time_value):
        qty_map = {}
        qty_products = products.with_company(self.company_id).with_context(
            to_date=date_time_value,
            allowed_company_ids=[self.company_id.id],
            company_owned=True,
        )
        for product in qty_products:
            qty_map[product.id] = product.qty_available
        return qty_map

    def _get_move_qty_map(self, products, start_dt, end_dt, source_usage_domain, dest_usage_domain):
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "done"),
            ("product_id", "in", products.ids),
            ("date", ">=", start_dt),
            ("date", "<=", end_dt),
            source_usage_domain,
            dest_usage_domain,
        ]
        move_lines = self.env["stock.move.line"].search(domain)
        qty_map = defaultdict(float)
        for line in move_lines:
            qty_map[line.product_id.id] += line.quantity
        return qty_map

    def _get_action_label(self, days_inventory, buy_threshold, liquidate_threshold):
        if days_inventory < buy_threshold:
            return _("COMPRAR")
        if days_inventory > liquidate_threshold:
            return _("LIQUIDAR")
        return _("OK")

    def _build_excel(self, snapshot):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        formats = self._get_workbook_formats(workbook)
        used_sheet_names = set()
        sheet_names = defaultdict(dict)

        for mode in snapshot["modes"]:
            for category_data in snapshot["categories"]:
                suffix = _("Mensual") if mode == "monthly" else _("Semanal")
                base_name = "%s_%s" % (category_data["name"], suffix)
                sheet_name = self._make_sheet_name(base_name, used_sheet_names)
                sheet_names[mode][category_data["id"]] = sheet_name
                self._write_category_sheet(
                    workbook=workbook,
                    sheet_name=sheet_name,
                    category_data=category_data,
                    periods=snapshot["periods_by_mode"][mode],
                    metrics=category_data["metrics"][mode],
                    snapshot=snapshot,
                    formats=formats,
                )

        self._write_dashboard_sheet(
            workbook=workbook,
            sheet_name="Dashboard",
            snapshot=snapshot,
            sheet_names=sheet_names[snapshot["dashboard_mode"]],
            formats=formats,
        )

        workbook.close()
        output.seek(0)
        return output

    def _get_workbook_formats(self, workbook):
        return {
            "title": workbook.add_format(
                {"bold": True, "font_size": 12, "align": "center", "valign": "vcenter"}
            ),
            "subtitle": workbook.add_format(
                {"italic": True, "font_size": 9, "align": "center"}
            ),
            "header": workbook.add_format(
                {
                    "bold": True,
                    "align": "center",
                    "valign": "vcenter",
                    "bg_color": "#1F4E78",
                    "font_color": "#FFFFFF",
                    "border": 1,
                    "text_wrap": True,
                }
            ),
            "label": workbook.add_format(
                {"bold": True, "border": 1, "bg_color": "#D9EAF7"}
            ),
            "number": workbook.add_format(
                {"border": 1, "num_format": "#,##0.00"}
            ),
            "currency": workbook.add_format(
                {"border": 1, "num_format": "₡#,##0.00"}
            ),
            "text": workbook.add_format({"border": 1}),
            "buy": workbook.add_format(
                {"border": 1, "bg_color": "#FDE9D9", "font_color": "#9C0006", "bold": True}
            ),
            "ok": workbook.add_format(
                {"border": 1, "bg_color": "#E2F0D9", "font_color": "#375623", "bold": True}
            ),
            "liquidate": workbook.add_format(
                {"border": 1, "bg_color": "#FFF2CC", "font_color": "#7F6000", "bold": True}
            ),
            "dashboard_header": workbook.add_format(
                {
                    "bold": True,
                    "align": "center",
                    "valign": "vcenter",
                    "bg_color": "#173F5F",
                    "font_color": "#FFFFFF",
                    "border": 1,
                }
            ),
            "dashboard_total": workbook.add_format(
                {
                    "bold": True,
                    "border": 1,
                    "bg_color": "#D9E2F3",
                    "num_format": "₡#,##0.00",
                }
            ),
            "dashboard_total_number": workbook.add_format(
                {
                    "bold": True,
                    "border": 1,
                    "bg_color": "#D9E2F3",
                    "num_format": "#,##0.00",
                }
            ),
            "dashboard_total_label": workbook.add_format(
                {"bold": True, "border": 1, "bg_color": "#D9E2F3"}
            ),
        }

    def _write_category_sheet(self, workbook, sheet_name, category_data, periods, metrics, snapshot, formats):
        sheet = workbook.add_worksheet(sheet_name)
        sheet.freeze_panes(3, 1)
        sheet.set_column(0, 0, 34)
        sheet.set_column(1, max(len(periods), 1), 14)

        row_specs = self._get_category_row_specs(snapshot["can_view_cost"])
        row_positions = {}
        last_col = len(periods)
        sheet.merge_range(
            0,
            0,
            0,
            last_col,
            _("Dashboard de Inventario - %(category)s") % {"category": category_data["display_name"]},
            formats["title"],
        )
        sheet.merge_range(
            1,
            0,
            1,
            last_col,
            _("%(company)s | Periodo %(date_from)s a %(date_to)s")
            % {
                "company": snapshot["company"].name,
                "date_from": snapshot["date_from"],
                "date_to": snapshot["date_to"],
            },
            formats["subtitle"],
        )

        sheet.write(2, 0, _("Concepto"), formats["header"])
        for index, period in enumerate(periods, start=1):
            sheet.write(2, index, period["label"], formats["header"])

        for zero_based_row, row_spec in enumerate(row_specs, start=3):
            row_positions[row_spec["key"]] = zero_based_row
            sheet.write(zero_based_row, 0, row_spec["label"], formats["label"])

        for col_index, metric in enumerate(metrics, start=1):
            for row_spec in row_specs:
                row_index = row_positions[row_spec["key"]]
                value = metric[row_spec["key"]]
                if row_spec["type"] == "text":
                    sheet.write(row_index, col_index, value, self._get_action_format(value, formats))
                else:
                    cell_format = formats["currency"] if row_spec["type"] == "currency" else formats["number"]
                    sheet.write_number(row_index, col_index, value or 0.0, cell_format)

        if periods:
            days_row = row_positions["days_inventory"]
            first_data_col = 1
            last_data_col = len(periods)
            sheet.conditional_format(
                days_row,
                first_data_col,
                days_row,
                last_data_col,
                {
                    "type": "cell",
                    "criteria": "<",
                    "value": category_data["buy_threshold"],
                    "format": formats["buy"],
                },
            )
            sheet.conditional_format(
                days_row,
                first_data_col,
                days_row,
                last_data_col,
                {
                    "type": "cell",
                    "criteria": "between",
                    "minimum": category_data["buy_threshold"],
                    "maximum": category_data["liquidate_threshold"],
                    "format": formats["liquidate"],
                },
            )
            sheet.conditional_format(
                days_row,
                first_data_col,
                days_row,
                last_data_col,
                {
                    "type": "cell",
                    "criteria": ">",
                    "value": category_data["liquidate_threshold"],
                    "format": formats["ok"],
                },
            )

    def _get_category_row_specs(self, can_view_cost):
        row_specs = [
            {"key": "opening_qty", "label": _("Inventario inicial (unid)"), "type": "number"},
            {"key": "incoming_qty", "label": _("Llegadas (unid)"), "type": "number"},
            {"key": "sales_qty", "label": _("Ventas (unid)"), "type": "number"},
            {"key": "closing_qty", "label": _("Inventario final (unid)"), "type": "number"},
            {"key": "avg_daily_qty", "label": _("Promedio diario (unid)"), "type": "number"},
            {"key": "days_inventory", "label": _("Dias inventario"), "type": "number"},
        ]
        if can_view_cost:
            row_specs.extend(
                [
                    {"key": "average_price", "label": _("Precio promedio ₡"), "type": "currency"},
                    {"key": "sales_value", "label": _("Ventas ₡"), "type": "currency"},
                    {"key": "inventory_value", "label": _("Inventario ₡"), "type": "currency"},
                ]
            )
        row_specs.extend(
            [
                {"key": "target_days", "label": _("Cobertura objetivo (dias)"), "type": "number"},
                {"key": "suggested_purchase", "label": _("Compra sugerida (unid)"), "type": "number"},
                {"key": "action", "label": _("Alerta compra"), "type": "text"},
            ]
        )
        return row_specs

    def _write_dashboard_sheet(self, workbook, sheet_name, snapshot, sheet_names, formats):
        sheet = workbook.add_worksheet(sheet_name)
        sheet.freeze_panes(1, 1)
        sheet.set_column(0, 0, 32)
        sheet.set_column(1, 4, 18)
        sheet.set_column(5, 5, 16)

        can_view_cost = snapshot["can_view_cost"]
        if can_view_cost:
            headers = [
                _("Categoria"),
                _("Ventas ₡ periodo"),
                _("Inventario ₡ actual"),
                _("Dias inventario"),
                _("Compra sugerida"),
                _("Accion"),
            ]
            sales_key = "sales_value"
            inventory_key = "inventory_value"
            total_format = formats["dashboard_total"]
            col_formats = {
                1: formats["currency"],
                2: formats["currency"],
                3: formats["number"],
                4: formats["number"],
                5: formats["text"],
            }
        else:
            headers = [
                _("Categoria"),
                _("Ventas unid periodo"),
                _("Inventario actual unid"),
                _("Dias inventario"),
                _("Compra sugerida"),
                _("Accion"),
            ]
            sales_key = "sales_qty"
            inventory_key = "closing_qty"
            total_format = formats["dashboard_total_number"]
            col_formats = {
                1: formats["number"],
                2: formats["number"],
                3: formats["number"],
                4: formats["number"],
                5: formats["text"],
            }

        for col, header in enumerate(headers):
            sheet.write(0, col, header, formats["dashboard_header"])

        source_periods = snapshot["periods_by_mode"][snapshot["dashboard_mode"]]
        last_period_col = len(source_periods)
        row_specs = self._get_category_row_specs(can_view_cost)
        row_refs = {spec["key"]: index + 4 for index, spec in enumerate(row_specs)}

        start_row = 1
        end_row = start_row
        for category_data in snapshot["categories"]:
            category_sheet = sheet_names.get(category_data["id"])
            if not category_sheet:
                continue

            quoted_sheet = self._quote_sheet_name(category_sheet)
            sales_start = "%s%s" % (xl_col_to_name(1), row_refs[sales_key])
            sales_end = "%s%s" % (xl_col_to_name(last_period_col), row_refs[sales_key])
            current_inventory = "%s%s" % (xl_col_to_name(last_period_col), row_refs[inventory_key])
            current_days = "%s%s" % (xl_col_to_name(last_period_col), row_refs["days_inventory"])
            current_purchase = "%s%s" % (xl_col_to_name(last_period_col), row_refs["suggested_purchase"])
            current_action = "%s%s" % (xl_col_to_name(last_period_col), row_refs["action"])

            sheet.write(end_row, 0, category_data["display_name"], formats["text"])
            sheet.write_formula(
                end_row,
                1,
                "=SUM(%s!%s:%s!%s)" % (quoted_sheet, sales_start, quoted_sheet, sales_end),
                col_formats[1],
            )
            sheet.write_formula(
                end_row,
                2,
                "=%s!%s" % (quoted_sheet, current_inventory),
                col_formats[2],
            )
            sheet.write_formula(
                end_row,
                3,
                "=%s!%s" % (quoted_sheet, current_days),
                col_formats[3],
            )
            sheet.write_formula(
                end_row,
                4,
                "=%s!%s" % (quoted_sheet, current_purchase),
                col_formats[4],
            )
            sheet.write_formula(
                end_row,
                5,
                "=%s!%s" % (quoted_sheet, current_action),
                col_formats[5],
            )
            end_row += 1

        if end_row > start_row:
            sheet.write(end_row, 0, _("TOTAL"), formats["dashboard_total_label"])
            sheet.write_formula(end_row, 1, "=SUM(B2:B%s)" % end_row, total_format)
            sheet.write_formula(end_row, 2, "=SUM(C2:C%s)" % end_row, total_format)
            sheet.write(end_row, 3, "", formats["dashboard_total_label"])
            sheet.write_formula(end_row, 4, "=SUM(E2:E%s)" % end_row, formats["dashboard_total_number"])
            sheet.write(end_row, 5, "", formats["dashboard_total_label"])

        sheet.conditional_format(
            1,
            5,
            max(end_row - 1, 1),
            5,
            {"type": "text", "criteria": "containing", "value": _("COMPRAR"), "format": formats["buy"]},
        )
        sheet.conditional_format(
            1,
            5,
            max(end_row - 1, 1),
            5,
            {"type": "text", "criteria": "containing", "value": _("LIQUIDAR"), "format": formats["liquidate"]},
        )
        sheet.conditional_format(
            1,
            5,
            max(end_row - 1, 1),
            5,
            {"type": "text", "criteria": "containing", "value": _("OK"), "format": formats["ok"]},
        )

    def _get_action_format(self, action, formats):
        if action == _("COMPRAR"):
            return formats["buy"]
        if action == _("LIQUIDAR"):
            return formats["liquidate"]
        return formats["ok"]

    def _make_sheet_name(self, base_name, used_sheet_names):
        sanitized = re.sub(r"[\[\]:*?/\\]", " ", base_name).strip() or _("Hoja")
        sanitized = sanitized[:31]
        candidate = sanitized
        suffix = 1
        while candidate in used_sheet_names:
            suffix_text = "_%s" % suffix
            candidate = "%s%s" % (sanitized[: 31 - len(suffix_text)], suffix_text)
            suffix += 1
        used_sheet_names.add(candidate)
        return candidate

    def _quote_sheet_name(self, sheet_name):
        return "'%s'" % sheet_name.replace("'", "''")
