# -*- coding: utf-8 -*-

import base64
import io
from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

try:
    import xlsxwriter
    from xlsxwriter.utility import xl_col_to_name
except ImportError:
    xlsxwriter = None
    xl_col_to_name = None


class PurchaseSuggestionReport(models.Model):
    _name = "purchase.suggestion.report"
    _description = "Reporte de Sugerido de Compras"
    _order = "create_date desc"

    name = fields.Char(
        string="Nombre",
        compute="_compute_name",
        store=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
    )
    warehouse_ids = fields.Many2many(
        comodel_name="stock.warehouse",
        string="Almacenes",
        help="Si se deja vacio, se incluyen todos los almacenes de la compania.",
    )
    category_ids = fields.Many2many(
        comodel_name="product.category",
        string="Categorias",
        help="Si se deja vacio, se incluyen todas las categorias.",
    )
    product_ids = fields.Many2many(
        comodel_name="product.product",
        string="Productos",
        domain="[('is_storable', '=', True)]",
        help="Si se deja vacio, se incluyen todos los productos almacenables.",
    )
    sales_history_months = fields.Integer(
        string="Meses de ventas",
        required=True,
        default=3,
        help="Cantidad de meses hacia atras que se contemplan para calcular ventas y promedio mensual.",
    )
    coverage_months = fields.Integer(
        string="Meses a cubrir",
        required=True,
        default=3,
        help="Cantidad de meses que se desea cubrir para calcular la demanda.",
    )
    date_to = fields.Date(
        string="Fecha final",
        required=True,
        default=fields.Date.context_today,
    )
    date_from = fields.Date(
        string="Fecha inicial",
        compute="_compute_date_from",
        store=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("generated", "Generado"),
        ],
        string="Estado",
        default="draft",
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name="purchase.suggestion.report.line",
        inverse_name="report_id",
        string="Lineas",
    )
    total_available_qty = fields.Float(
        string="Total Cantidad",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )
    total_sale_qty = fields.Float(
        string="Total Venta",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )
    total_demand_qty = fields.Float(
        string="Total Demanda",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )
    total_suggested_purchase_qty = fields.Float(
        string="Total Sugerido",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )
    excel_file = fields.Binary(string="Archivo Excel", readonly=True)
    excel_filename = fields.Char(string="Nombre Excel", readonly=True)

    @api.depends("company_id", "sales_history_months", "coverage_months", "date_to")
    def _compute_name(self):
        for report in self:
            if report.company_id and report.date_to:
                report.name = _(
                    "Sugerido de Compras - %(company)s - %(date)s"
                ) % {
                    "company": report.company_id.name,
                    "date": report.date_to.strftime("%d/%m/%Y"),
                }
            else:
                report.name = _("Sugerido de Compras")

    @api.depends("sales_history_months", "date_to")
    def _compute_date_from(self):
        for report in self:
            if report.sales_history_months and report.date_to:
                report.date_from = report.date_to - relativedelta(
                    months=report.sales_history_months
                )
            else:
                report.date_from = False

    @api.depends(
        "line_ids.available_qty",
        "line_ids.total_sale_qty",
        "line_ids.demand_qty",
        "line_ids.suggested_purchase_qty",
    )
    def _compute_totals(self):
        for report in self:
            report.total_available_qty = sum(report.line_ids.mapped("available_qty"))
            report.total_sale_qty = sum(report.line_ids.mapped("total_sale_qty"))
            report.total_demand_qty = sum(report.line_ids.mapped("demand_qty"))
            report.total_suggested_purchase_qty = sum(
                report.line_ids.mapped("suggested_purchase_qty")
            )

    @api.constrains("sales_history_months", "coverage_months")
    def _check_months(self):
        for report in self:
            if report.sales_history_months <= 0:
                raise ValidationError(_("Los meses de ventas deben ser mayores a cero."))
            if report.coverage_months <= 0:
                raise ValidationError(_("Los meses a cubrir deben ser mayores a cero."))

    def action_generate_report(self):
        self.ensure_one()
        self._generate_lines()
        self.write(
            {
                "state": "generated",
                "excel_file": False,
                "excel_filename": False,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_reset_to_draft(self):
        self.ensure_one()
        self.line_ids.unlink()
        self.write(
            {
                "state": "draft",
                "excel_file": False,
                "excel_filename": False,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_export_excel(self):
        self.ensure_one()
        if self.state != "generated":
            raise UserError(_("Primero debe generar el reporte."))
        if not xlsxwriter:
            raise UserError(
                _("La libreria Python 'xlsxwriter' es necesaria para generar este reporte.")
            )

        output = self._build_excel()
        filename = "sugerido_compras_%s.xlsx" % fields.Date.to_string(self.date_to)
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

    def _generate_lines(self):
        self.ensure_one()
        self.line_ids.unlink()

        products = self._get_products()
        if not products:
            raise UserError(_("No se encontraron productos para los filtros seleccionados."))

        available_qty_map = self._get_available_qty_map(products)
        sale_qty_map = self._get_sale_qty_map(products)
        lines = []

        for product in products:
            available_qty = available_qty_map.get(product.id, 0.0)
            total_sale_qty = sale_qty_map.get(product.id, 0.0)
            average_monthly_qty = total_sale_qty / self.sales_history_months
            supply_months = (
                available_qty / average_monthly_qty
                if average_monthly_qty
                else 0.0
            )
            demand_qty = average_monthly_qty * self.coverage_months
            suggested_purchase_qty = demand_qty - available_qty

            if (
                not available_qty
                and not total_sale_qty
                and not demand_qty
                and not suggested_purchase_qty
            ):
                continue

            lines.append(
                {
                    "report_id": self.id,
                    "product_id": product.id,
                    "default_code": product.default_code or "",
                    "product_name": product.with_context(
                        display_default_code=False
                    ).display_name,
                    "uom_id": product.uom_id.id,
                    "available_qty": available_qty,
                    "total_sale_qty": total_sale_qty,
                    "average_monthly_qty": average_monthly_qty,
                    "supply_months": supply_months,
                    "demand_qty": demand_qty,
                    "suggested_purchase_qty": suggested_purchase_qty,
                }
            )

        if not lines:
            raise UserError(_("No hay datos para mostrar con los filtros seleccionados."))
        self.env["purchase.suggestion.report.line"].create(lines)

    def _get_products(self):
        self.ensure_one()
        domain = [("is_storable", "=", True), ("active", "=", True)]
        if self.product_ids:
            domain.append(("id", "in", self.product_ids.ids))
        if self.category_ids:
            domain.append(("categ_id", "child_of", self.category_ids.ids))
        return self.env["product.product"].with_company(self.company_id).search(
            domain,
            order="default_code, name, id",
        )

    def _get_location_domain(self):
        self.ensure_one()
        if self.warehouse_ids:
            locations = self.env["stock.location"].search(
                [
                    ("id", "child_of", self.warehouse_ids.mapped("view_location_id").ids),
                    ("usage", "=", "internal"),
                ]
            )
            return [("location_id", "in", locations.ids)]
        return [("location_id.usage", "=", "internal")]

    def _get_available_qty_map(self, products):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("product_id", "in", products.ids),
        ] + self._get_location_domain()
        groups = self.env["stock.quant"].read_group(
            domain=domain,
            fields=["product_id", "quantity:sum", "reserved_quantity:sum"],
            groupby=["product_id"],
        )
        qty_map = {}
        for group in groups:
            product_id = group["product_id"][0] if group.get("product_id") else False
            if product_id:
                qty_map[product_id] = (
                    group.get("quantity", 0.0)
                    - group.get("reserved_quantity", 0.0)
                )
        return qty_map

    def _get_sale_qty_map(self, products):
        self.ensure_one()
        date_from = datetime.combine(self.date_from, time.min)
        date_to = datetime.combine(self.date_to, time.max)
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "done"),
            ("product_id", "in", products.ids),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("location_id.usage", "=", "internal"),
            ("location_dest_id.usage", "=", "customer"),
        ]
        if self.warehouse_ids:
            locations = self.env["stock.location"].search(
                [
                    ("id", "child_of", self.warehouse_ids.mapped("view_location_id").ids),
                    ("usage", "=", "internal"),
                ]
            )
            domain.append(("location_id", "in", locations.ids))

        groups = self.env["stock.move.line"].read_group(
            domain=domain,
            fields=["product_id", "quantity_product_uom:sum"],
            groupby=["product_id"],
        )
        qty_map = {}
        for group in groups:
            product_id = group["product_id"][0] if group.get("product_id") else False
            if product_id:
                qty_map[product_id] = group.get("quantity_product_uom", 0.0)
        return qty_map

    def _build_excel(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet(_("Sugerido Compras"))

        formats = self._get_excel_formats(workbook)
        worksheet.merge_range(0, 0, 0, 8, self.name, formats["title"])
        worksheet.write(1, 0, _("Compania"), formats["label"])
        worksheet.write(1, 1, self.company_id.name, formats["text"])
        worksheet.write(2, 0, _("Periodo ventas"), formats["label"])
        worksheet.write(
            2,
            1,
            "%s - %s" % (self.date_from, self.date_to),
            formats["text"],
        )
        worksheet.write(3, 0, _("Meses ventas"), formats["label"])
        worksheet.write(3, 1, self.sales_history_months, formats["integer"])
        worksheet.write(4, 0, _("Meses a cubrir"), formats["label"])
        worksheet.write(4, 1, self.coverage_months, formats["integer"])

        headers = [
            _("Codigo"),
            _("Nombre"),
            _("Unidad"),
            _("Cantidad"),
            _("Total Venta"),
            _("Promedio Mensual"),
            _("Meses Abastecimiento"),
            _("Demanda"),
            _("Sugerido de Compras"),
        ]
        header_row = 6
        for col, header in enumerate(headers):
            worksheet.write(header_row, col, header, formats["header"])

        row = header_row + 1
        for line in self.line_ids.sorted(
            key=lambda item: (item.default_code or "", item.product_name or "")
        ):
            worksheet.write(row, 0, line.default_code or "", formats["text"])
            worksheet.write(row, 1, line.product_name or "", formats["text"])
            worksheet.write(row, 2, line.uom_id.name or "", formats["text"])
            worksheet.write(row, 3, line.available_qty, formats["number"])
            worksheet.write(row, 4, line.total_sale_qty, formats["number"])
            worksheet.write(row, 5, line.average_monthly_qty, formats["number"])
            worksheet.write(row, 6, line.supply_months, formats["number"])
            worksheet.write(row, 7, line.demand_qty, formats["number"])
            worksheet.write(row, 8, line.suggested_purchase_qty, formats["number"])
            row += 1

        if row > header_row + 1:
            worksheet.write(row, 2, _("Totales"), formats["total_label"])
            for col in (3, 4, 7, 8):
                col_letter = xl_col_to_name(col)
                worksheet.write_formula(
                    row,
                    col,
                    "=SUM(%s%d:%s%d)"
                    % (col_letter, header_row + 2, col_letter, row),
                    formats["total_number"],
                )

        worksheet.freeze_panes(header_row + 1, 0)
        worksheet.autofilter(header_row, 0, max(row, header_row + 1), 8)
        worksheet.set_column(0, 0, 16)
        worksheet.set_column(1, 1, 42)
        worksheet.set_column(2, 2, 12)
        worksheet.set_column(3, 8, 18)

        workbook.close()
        output.seek(0)
        return output

    def _get_excel_formats(self, workbook):
        return {
            "title": workbook.add_format(
                {"bold": True, "font_size": 14, "align": "center", "valign": "vcenter"}
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
            "label": workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1}),
            "text": workbook.add_format({"border": 1}),
            "integer": workbook.add_format({"border": 1, "num_format": "0"}),
            "number": workbook.add_format({"border": 1, "num_format": "#,##0.00"}),
            "total_label": workbook.add_format(
                {"bold": True, "border": 1, "bg_color": "#D9EAD3"}
            ),
            "total_number": workbook.add_format(
                {"bold": True, "border": 1, "bg_color": "#D9EAD3", "num_format": "#,##0.00"}
            ),
        }


class PurchaseSuggestionReportLine(models.Model):
    _name = "purchase.suggestion.report.line"
    _description = "Linea de Reporte de Sugerido de Compras"
    _order = "default_code, product_name, id"

    report_id = fields.Many2one(
        comodel_name="purchase.suggestion.report",
        string="Reporte",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto",
        readonly=True,
    )
    default_code = fields.Char(string="Codigo", readonly=True)
    product_name = fields.Char(string="Nombre", readonly=True)
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unidad",
        readonly=True,
    )
    available_qty = fields.Float(
        string="Cantidad",
        digits="Product Unit of Measure",
        readonly=True,
    )
    total_sale_qty = fields.Float(
        string="Total Venta",
        digits="Product Unit of Measure",
        readonly=True,
    )
    average_monthly_qty = fields.Float(
        string="Promedio Mensual",
        digits="Product Unit of Measure",
        readonly=True,
    )
    supply_months = fields.Float(
        string="Meses Abastecimiento",
        digits=(16, 2),
        readonly=True,
    )
    demand_qty = fields.Float(
        string="Demanda",
        digits="Product Unit of Measure",
        readonly=True,
    )
    suggested_purchase_qty = fields.Float(
        string="Sugerido de Compras",
        digits="Product Unit of Measure",
        readonly=True,
    )
