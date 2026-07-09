# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, content_disposition
import io
import xlsxwriter
from datetime import datetime


class StockLocationReportController(http.Controller):

    @http.route("/stock_location_report/export/<int:report_id>", type="http", auth="user")
    def export_excel(self, report_id, **kwargs):
        report = request.env["stock.location.report"].browse(report_id)
        if not report.exists() or report.state != "generated":
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        # Estilos
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#366092",
            "font_color": "white",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        subheader_format = workbook.add_format({
            "bold": True,
            "bg_color": "#B4C7E7",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        cell_format = workbook.add_format({
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })
        number_format = workbook.add_format({
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "num_format": "#,##0.00",
        })
        title_format = workbook.add_format({
            "bold": True,
            "font_size": 14,
            "font_color": "#366092",
            "align": "center",
            "valign": "vcenter",
        })

        # ==================== HOJA 1: RESUMEN ====================
        ws_summary = workbook.add_worksheet("Resumen")

        ws_summary.merge_range("A1:H1", "REPORTE DE MOVIMIENTOS POR UBICACIÓN", title_format)

        row = 2
        warehouse_names = ", ".join(report.warehouse_ids.mapped("name")) if report.warehouse_ids else ""
        ws_summary.write(row, 0, "Almacén(es):", subheader_format)
        ws_summary.write(row, 1, warehouse_names, cell_format)
        ws_summary.write(row, 3, "Ubicación:", subheader_format)
        ws_summary.write(row, 4, report.location_id.name if report.location_id else "Todas", cell_format)
        row += 1
        ws_summary.write(row, 0, "Producto:", subheader_format)
        ws_summary.write(row, 1, report.product_id.display_name if report.product_id else "Todos", cell_format)
        row += 1
        ws_summary.write(row, 0, "Fecha Desde:", subheader_format)
        ws_summary.write(row, 1, report.date_from.strftime("%d/%m/%Y"), cell_format)
        ws_summary.write(row, 3, "Fecha Hasta:", subheader_format)
        ws_summary.write(row, 4, report.date_to.strftime("%d/%m/%Y"), cell_format)
        row += 1
        ws_summary.write(row, 0, "Fecha de Generación:", subheader_format)
        ws_summary.write(row, 1, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), cell_format)

        row += 2
        ws_summary.merge_range(row, 0, row, 1, "TOTALES", subheader_format)
        row += 1

        for col, header in enumerate(["Concepto", "Cantidad"]):
            ws_summary.write(row, col, header, header_format)
        row += 1

        totals_data = [
            ("Total Saldo Inicial", report.total_saldo_inicial),
            ("Total Entradas", report.total_entradas),
            ("Total Salidas", report.total_salidas),
            ("Movimiento Neto", report.total_entradas - report.total_salidas),
            ("Total Físico", report.total_fisico),
            ("Total Reservado", report.total_reservado),
            ("Total Disponible", report.total_disponible),
        ]

        if report._includes_initial_load():
            ws_summary.write(
                row,
                3,
                "Carga inicial:",
                subheader_format,
            )
            ws_summary.write(
                row,
                4,
                "Incluida desde 01/04/2026",
                cell_format,
            )

        for concepto, cantidad in totals_data:
            ws_summary.write(row, 0, concepto, cell_format)
            ws_summary.write(row, 1, cantidad, number_format)
            row += 1

        ws_summary.set_column("A:A", 25)
        ws_summary.set_column("B:B", 15)
        ws_summary.set_column("C:H", 15)

        # ==================== HOJA 2: DETALLE POR PRODUCTO ====================
        ws_detail = workbook.add_worksheet("Detalle por Producto")
        ws_detail.merge_range("A1:J1", "DETALLE POR PRODUCTO", title_format)

        row = 2
        headers = [
            "Código", "Producto", "Unidad", "Saldo Inicial", "Entradas",
            "Salidas", "Mov. Neto", "Cant. Física", "Reservado", "Disponible"
        ]
        for col, header in enumerate(headers):
            ws_detail.write(row, col, header, header_format)

        row += 1
        for line in report.line_ids:
            ws_detail.write(row, 0, line.default_code or "", cell_format)
            ws_detail.write(row, 1, line.product_name or "", cell_format)
            ws_detail.write(row, 2, line.uom_id.name if line.uom_id else "", cell_format)
            ws_detail.write(row, 3, line.saldo_inicial_qty, number_format)
            ws_detail.write(row, 4, line.entradas_qty, number_format)
            ws_detail.write(row, 5, line.salidas_qty, number_format)
            ws_detail.write(row, 6, line.movimiento_net, number_format)
            ws_detail.write(row, 7, line.fisico_qty, number_format)
            ws_detail.write(row, 8, line.reservado_qty, number_format)
            ws_detail.write(row, 9, line.disponible_qty, number_format)
            row += 1

        ws_detail.set_column("A:A", 15)
        ws_detail.set_column("B:B", 40)
        ws_detail.set_column("C:C", 12)
        ws_detail.set_column("D:J", 15)

        # ==================== HOJA 3: POR BODEGA ====================
        ws_wh = workbook.add_worksheet("Por Bodega")
        ws_wh.merge_range("A1:J1", "DESGLOSE POR BODEGA", title_format)

        row = 2
        headers_wh = [
            "Código", "Producto", "Almacén", "Unidad",
            "Saldo Inicial", "Entradas", "Salidas",
            "Cant. Física", "Reservado", "Disponible"
        ]
        for col, header in enumerate(headers_wh):
            ws_wh.write(row, col, header, header_format)

        row += 1
        for wline in report.warehouse_line_ids:
            ws_wh.write(row, 0, wline.default_code or "", cell_format)
            ws_wh.write(row, 1, wline.product_name or "", cell_format)
            ws_wh.write(row, 2, wline.warehouse_name or "", cell_format)
            ws_wh.write(row, 3, wline.uom_id.name if wline.uom_id else "", cell_format)
            ws_wh.write(row, 4, wline.saldo_inicial_qty, number_format)
            ws_wh.write(row, 5, wline.entradas_qty, number_format)
            ws_wh.write(row, 6, wline.salidas_qty, number_format)
            ws_wh.write(row, 7, wline.fisico_qty, number_format)
            ws_wh.write(row, 8, wline.reservado_qty, number_format)
            ws_wh.write(row, 9, wline.disponible_qty, number_format)
            row += 1

        ws_wh.set_column("A:A", 15)
        ws_wh.set_column("B:B", 40)
        ws_wh.set_column("C:C", 25)
        ws_wh.set_column("D:D", 12)
        ws_wh.set_column("E:J", 15)

        # ==================== HOJA 4: ENTRADAS ====================
        ws_ent = workbook.add_worksheet("Entradas")
        ws_ent.merge_range("A1:J1", "MOVIMIENTOS DE ENTRADA", title_format)

        row = 2
        headers_ent = [
            "Fecha", "Referencia", "Origen", "Producto", "Código",
            "Cantidad", "UoM", "Ubicación Origen", "Ubicación Destino", "Estado"
        ]
        for col, header in enumerate(headers_ent):
            ws_ent.write(row, col, header, header_format)

        row += 1
        date_from = datetime.combine(report.date_from, datetime.min.time())
        date_to = datetime.combine(report.date_to, datetime.max.time())

        location_domain = report._get_location_domain()
        location_ids = request.env["stock.location"].search(location_domain)

        move_domain = [
            ("location_dest_id", "in", location_ids.ids),
            ("state", "=", "done"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]
        if report.product_id:
            move_domain.append(("product_id", "=", report.product_id.id))

        initial_load_rows = report._get_initial_load_export_rows(location_ids)
        for initial_row in initial_load_rows:
            if report.product_id and initial_row["product_id"] != report.product_id.id:
                continue
            ws_ent.write(row, 0, initial_row["date"].strftime("%d/%m/%Y %H:%M"), cell_format)
            ws_ent.write(row, 1, initial_row["reference"], cell_format)
            ws_ent.write(row, 2, initial_row["origin"], cell_format)
            ws_ent.write(row, 3, initial_row["product_name"], cell_format)
            ws_ent.write(row, 4, initial_row["default_code"], cell_format)
            ws_ent.write(row, 5, initial_row["quantity"], number_format)
            ws_ent.write(row, 6, initial_row["uom_name"], cell_format)
            ws_ent.write(row, 7, "Carga inicial", cell_format)
            ws_ent.write(row, 8, initial_row["location_name"], cell_format)
            ws_ent.write(row, 9, initial_row["state"], cell_format)
            row += 1

        moves = request.env["stock.move"].search(move_domain, order="date desc")

        for move in moves:
            ws_ent.write(row, 0, move.date.strftime("%d/%m/%Y %H:%M") if move.date else "", cell_format)
            ws_ent.write(row, 1, move.reference or "", cell_format)
            ws_ent.write(row, 2, move.origin or "", cell_format)
            ws_ent.write(row, 3, move.product_id.name or "", cell_format)
            ws_ent.write(row, 4, move.product_id.default_code or "", cell_format)
            ws_ent.write(row, 5, move.quantity, number_format)
            ws_ent.write(row, 6, move.product_uom.name if move.product_uom else "", cell_format)
            ws_ent.write(row, 7, move.location_id.complete_name or "", cell_format)
            ws_ent.write(row, 8, move.location_dest_id.complete_name or "", cell_format)
            ws_ent.write(row, 9, move.state or "", cell_format)
            row += 1

        ws_ent.set_column("A:A", 18)
        ws_ent.set_column("B:C", 20)
        ws_ent.set_column("D:D", 35)
        ws_ent.set_column("E:E", 15)
        ws_ent.set_column("F:F", 12)
        ws_ent.set_column("G:G", 10)
        ws_ent.set_column("H:I", 30)
        ws_ent.set_column("J:J", 12)

        # ==================== HOJA 5: SALIDAS ====================
        ws_sal = workbook.add_worksheet("Salidas")
        ws_sal.merge_range("A1:J1", "MOVIMIENTOS DE SALIDA", title_format)

        row = 2
        for col, header in enumerate(headers_ent):
            ws_sal.write(row, col, header, header_format)

        row += 1
        move_domain = [
            ("location_id", "in", location_ids.ids),
            ("state", "=", "done"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]
        if report.product_id:
            move_domain.append(("product_id", "=", report.product_id.id))

        moves = request.env["stock.move"].search(move_domain, order="date desc")

        for move in moves:
            ws_sal.write(row, 0, move.date.strftime("%d/%m/%Y %H:%M") if move.date else "", cell_format)
            ws_sal.write(row, 1, move.reference or "", cell_format)
            ws_sal.write(row, 2, move.origin or "", cell_format)
            ws_sal.write(row, 3, move.product_id.name or "", cell_format)
            ws_sal.write(row, 4, move.product_id.default_code or "", cell_format)
            ws_sal.write(row, 5, move.quantity, number_format)
            ws_sal.write(row, 6, move.product_uom.name if move.product_uom else "", cell_format)
            ws_sal.write(row, 7, move.location_id.complete_name or "", cell_format)
            ws_sal.write(row, 8, move.location_dest_id.complete_name or "", cell_format)
            ws_sal.write(row, 9, move.state or "", cell_format)
            row += 1

        ws_sal.set_column("A:A", 18)
        ws_sal.set_column("B:C", 20)
        ws_sal.set_column("D:D", 35)
        ws_sal.set_column("E:E", 15)
        ws_sal.set_column("F:F", 12)
        ws_sal.set_column("G:G", 10)
        ws_sal.set_column("H:I", 30)
        ws_sal.set_column("J:J", 12)

        # ==================== HOJA 6: RESERVAS ====================
        ws_res = workbook.add_worksheet("Reservas")
        ws_res.merge_range("A1:H1", "RESERVAS ACTUALES (QUANTS)", title_format)

        row = 2
        headers_res = [
            "Producto", "Código", "Cantidad Física", "Cantidad Reservada",
            "Cantidad Disponible", "Unidad", "Ubicación", "Lote"
        ]
        for col, header in enumerate(headers_res):
            ws_res.write(row, col, header, header_format)

        row += 1
        quant_domain = [
            ("location_id", "in", location_ids.ids),
            "|",
            ("quantity", ">", 0),
            ("reserved_quantity", ">", 0),
        ]
        if report.product_id:
            quant_domain.append(("product_id", "=", report.product_id.id))

        quants = request.env["stock.quant"].search(quant_domain)

        for quant in quants:
            ws_res.write(row, 0, quant.product_id.name or "", cell_format)
            ws_res.write(row, 1, quant.product_id.default_code or "", cell_format)
            ws_res.write(row, 2, quant.quantity, number_format)
            ws_res.write(row, 3, quant.reserved_quantity, number_format)
            ws_res.write(row, 4, quant.quantity - quant.reserved_quantity, number_format)
            ws_res.write(row, 5, quant.product_uom_id.name if quant.product_uom_id else "", cell_format)
            ws_res.write(row, 6, quant.location_id.complete_name or "", cell_format)
            ws_res.write(row, 7, quant.lot_id.name if quant.lot_id else "", cell_format)
            row += 1

        ws_res.set_column("A:A", 35)
        ws_res.set_column("B:B", 15)
        ws_res.set_column("C:E", 18)
        ws_res.set_column("F:F", 12)
        ws_res.set_column("G:G", 30)
        ws_res.set_column("H:H", 15)

        workbook.close()
        output.seek(0)

        warehouse_filename = "_".join(report.warehouse_ids.mapped("name")) if report.warehouse_ids else "SinAlmacen"
        product_filename = ("_" + report.product_id.default_code) if report.product_id and report.product_id.default_code else ""
        filename = "Reporte_Movimientos_%s%s_%s_a_%s.xlsx" % (
            warehouse_filename.replace(" ", "_").replace(",", ""),
            product_filename.replace(" ", "_"),
            report.date_from.strftime("%Y%m%d"),
            report.date_to.strftime("%Y%m%d"),
        )

        return request.make_response(
            output.read(),
            headers=[
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", content_disposition(filename)),
            ],
        )
