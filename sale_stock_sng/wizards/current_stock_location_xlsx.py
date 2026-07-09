# -*- coding: utf-8 -*-
from odoo import models, _


class CurrentStockLocationXlsx(models.AbstractModel):
    _name = "report.sale_stock_sng.current_stock_location_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "XLSX - Existencias Actuales por Ubicacion"

    def generate_xlsx_report(self, workbook, data, wizards):
        title_fmt = workbook.add_format({"bold": True, "font_size": 13})
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#DDDDDD"})
        text_fmt = workbook.add_format({"text_wrap": True})
        qty_fmt = workbook.add_format({"num_format": "#,##0.00"})
        money_fmt = workbook.add_format({"num_format": "#,##0.00"})

        for wizard in wizards:
            ws = workbook.add_worksheet(_("Existencias actuales"))
            row = 0

            ws.write(row, 0, _("REPORTE DE EXISTENCIAS ACTUALES POR UBICACION"), title_fmt)
            row += 2

            ws.write(row, 0, _("Clientes"))
            ws.write(row, 1, ", ".join(wizard.partner_ids.mapped("name")) if wizard.partner_ids else _("Todos"))
            row += 1
            ws.write(row, 0, _("Vendedor"))
            ws.write(row, 1, wizard.user_id.name if wizard.user_id else _("Todos"))
            row += 1
            ws.write(row, 0, _("Bodegas"))
            ws.write(row, 1, ", ".join(wizard.location_ids.mapped("complete_name")) if wizard.location_ids else _("Todas"))
            row += 1
            ws.write(row, 0, _("Productos"))
            ws.write(row, 1, ", ".join(wizard.product_ids.mapped("display_name")) if wizard.product_ids else _("Todos"))
            row += 2

            headers = [
                _("Codigo de cliente"),
                _("Cliente"),
                _("Ubicacion / bodega cliente"),
                _("Codigo producto"),
                _("Producto"),
                _("Cantidad actual"),
                _("Cantidad reservada"),
                _("Cantidad disponible"),
                _("Precio Venta unitario"),
                _("Valor total"),
                _("Vendedor"),
                _("Ruta"),
            ]
            for col, header in enumerate(headers):
                ws.write(row, col, header, header_fmt)
            header_row = row
            row += 1

            total_value = 0.0
            for report_row in wizard._get_report_rows():
                partner = report_row["partner"]
                location = report_row["location"]
                product = report_row["product"]
                total_value += report_row["total_value"]

                ws.write(row, 0, report_row["client_code"])
                ws.write(row, 1, partner.name or "", text_fmt)
                ws.write(row, 2, location.complete_name or "", text_fmt)
                ws.write(row, 3, report_row["product_code"])
                ws.write(row, 4, product.display_name or "", text_fmt)
                ws.write_number(row, 5, report_row["quantity"], qty_fmt)
                ws.write_number(row, 6, report_row["reserved"], qty_fmt)
                ws.write_number(row, 7, report_row["available"], qty_fmt)
                ws.write_number(row, 8, report_row["sale_price"], money_fmt)
                ws.write_number(row, 9, report_row["total_value"], money_fmt)
                ws.write(row, 10, report_row["salesperson_name"])
                ws.write(row, 11, report_row["route_name"])
                row += 1

            ws.write(row, 0, _("TOTAL"), header_fmt)
            ws.write_number(row, 9, total_value, money_fmt)

            widths = [16, 35, 42, 18, 42, 16, 18, 18, 20, 18, 22, 22]
            for index, width in enumerate(widths):
                ws.set_column(index, index, width)
            ws.freeze_panes(header_row + 1, 0)
            ws.autofilter(header_row, 0, max(row, header_row + 1), len(headers) - 1)
