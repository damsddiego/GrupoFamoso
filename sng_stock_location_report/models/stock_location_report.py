# -*- coding: utf-8 -*-
from datetime import date, datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockLocationReport(models.Model):
    _name = "stock.location.report"
    _description = "Reporte de Movimientos por Ubicación"
    _order = "create_date desc"

    INITIAL_LOAD_DATE = date(2026, 4, 1)

    name = fields.Char(
        string="Nombre",
        compute="_compute_name",
        store=True,
    )
    warehouse_ids = fields.Many2many(
        comodel_name="stock.warehouse",
        string="Almacenes",
        required=True,
        help="Seleccione uno o más almacenes para filtrar las ubicaciones",
    )
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Ubicación",
        domain="[('warehouse_id', 'in', warehouse_ids)]",
        help="Deje vacío para incluir todas las ubicaciones de los almacenes seleccionados",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto",
        help="Deje vacío para incluir todos los productos",
    )
    date_from = fields.Date(
        string="Fecha Desde",
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
    )
    date_to = fields.Date(
        string="Fecha Hasta",
        required=True,
        default=lambda self: fields.Date.today(),
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
        comodel_name="stock.location.report.line",
        inverse_name="report_id",
        string="Líneas de Reporte",
    )
    warehouse_line_ids = fields.One2many(
        comodel_name="stock.location.report.warehouse.line",
        inverse_name="report_id",
        string="Desglose por Bodega",
    )

    # Totales
    total_entradas = fields.Float(
        string="Total Entradas",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )
    total_saldo_inicial = fields.Float(
        string="Total Saldo Inicial",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )
    total_salidas = fields.Float(
        string="Total Salidas",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )
    total_reservado = fields.Float(
        string="Total Reservado",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )
    total_fisico = fields.Float(
        string="Total Físico",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )
    total_disponible = fields.Float(
        string="Total Disponible",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
    )

    @api.depends("warehouse_ids", "date_from", "date_to")
    def _compute_name(self):
        for report in self:
            if report.warehouse_ids and report.date_from and report.date_to:
                warehouse_names = ", ".join(report.warehouse_ids.mapped("name"))
                report.name = _(
                    "%(warehouses)s - %(from)s a %(to)s"
                ) % {
                    "warehouses": warehouse_names,
                    "from": report.date_from.strftime("%d/%m/%Y"),
                    "to": report.date_to.strftime("%d/%m/%Y"),
                }
            else:
                report.name = _("Nuevo Reporte")

    @api.depends(
        "line_ids.saldo_inicial_qty",
        "line_ids.entradas_qty",
        "line_ids.salidas_qty",
        "line_ids.reservado_qty",
        "line_ids.fisico_qty",
        "line_ids.disponible_qty",
    )
    def _compute_totals(self):
        for report in self:
            report.total_saldo_inicial = sum(
                line.saldo_inicial_qty for line in report.line_ids
            )
            report.total_entradas = sum(
                line.entradas_qty for line in report.line_ids
            )
            report.total_salidas = sum(
                line.salidas_qty for line in report.line_ids
            )
            report.total_reservado = sum(
                line.reservado_qty for line in report.line_ids
            )
            report.total_fisico = sum(
                line.fisico_qty for line in report.line_ids
            )
            report.total_disponible = sum(
                line.disponible_qty for line in report.line_ids
            )

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for report in self:
            if report.date_from and report.date_to:
                if report.date_from > report.date_to:
                    raise UserError(_(
                        "La fecha 'Desde' no puede ser mayor que la fecha 'Hasta'"
                    ))

    def action_generate_report(self):
        self.ensure_one()
        self._generate_lines()
        self.state = "generated"
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.location.report",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_reset_to_draft(self):
        self.ensure_one()
        self.line_ids.unlink()
        self.warehouse_line_ids.unlink()
        self.state = "draft"
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.location.report",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _get_location_domain(self):
        """Obtiene el dominio de ubicaciones a consultar"""
        self.ensure_one()
        if self.location_id:
            return [("id", "=", self.location_id.id)]
        else:
            warehouses = self.warehouse_ids
            location_ids = self.env["stock.location"].search([
                ("id", "child_of", warehouses.mapped("view_location_id").ids),
                ("usage", "=", "internal"),
            ])
            return [("id", "in", location_ids.ids)]

    def _get_initial_load_bounds(self):
        self.ensure_one()
        return (
            datetime.combine(self.INITIAL_LOAD_DATE, time.min),
            datetime.combine(self.INITIAL_LOAD_DATE, time.max),
        )

    def _includes_initial_load(self):
        self.ensure_one()
        return self.date_from <= self.INITIAL_LOAD_DATE <= self.date_to

    def _get_current_quantities(self, product_id, location_ids_tuple):
        self.ensure_one()
        self._cr.execute("""
            SELECT
                COALESCE(SUM(quantity), 0) as fisico,
                COALESCE(SUM(reserved_quantity), 0) as reservado
            FROM stock_quant
            WHERE product_id = %(product_id)s
              AND location_id IN %(location_ids)s
        """, {
            "product_id": product_id,
            "location_ids": location_ids_tuple,
        })
        result = self._cr.fetchone()
        return (result[0] or 0.0, result[1] or 0.0)

    def _get_stock_at_datetime(self, product_id, location_ids_tuple, snapshot_dt, inclusive):
        self.ensure_one()
        fisico_actual, _reservado = self._get_current_quantities(
            product_id, location_ids_tuple
        )
        operator = ">=" if inclusive else ">"
        self._cr.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN location_dest_id IN %(location_ids)s THEN quantity ELSE 0 END), 0) as entradas,
                COALESCE(SUM(CASE WHEN location_id IN %(location_ids)s THEN quantity ELSE 0 END), 0) as salidas
            FROM stock_move
            WHERE product_id = %(product_id)s
              AND state = 'done'
              AND date {operator} %(snapshot_dt)s
              AND (
                  location_id IN %(location_ids)s
                  OR location_dest_id IN %(location_ids)s
              )
        """.format(operator=operator), {
            "product_id": product_id,
            "location_ids": location_ids_tuple,
            "snapshot_dt": snapshot_dt,
        })
        entradas_posteriores, salidas_posteriores = self._cr.fetchone()
        return (
            (fisico_actual or 0.0)
            - (entradas_posteriores or 0.0)
            + (salidas_posteriores or 0.0)
        )

    def _has_initial_load_quant(self, product_id, location_ids_tuple):
        self.ensure_one()
        initial_start, initial_end = self._get_initial_load_bounds()
        self._cr.execute("""
            SELECT 1
            FROM stock_quant
            WHERE product_id = %(product_id)s
              AND location_id IN %(location_ids)s
              AND (
                  (create_date >= %(initial_start)s AND create_date <= %(initial_end)s)
                  OR (in_date >= %(initial_start)s AND in_date <= %(initial_end)s)
              )
            LIMIT 1
        """, {
            "product_id": product_id,
            "location_ids": location_ids_tuple,
            "initial_start": initial_start,
            "initial_end": initial_end,
        })
        return bool(self._cr.fetchone())

    def _get_initial_load_qty(self, product_id, location_ids_tuple):
        self.ensure_one()
        if not self._includes_initial_load():
            return 0.0
        if not self._has_initial_load_quant(product_id, location_ids_tuple):
            return 0.0
        _initial_start, initial_end = self._get_initial_load_bounds()
        return self._get_stock_at_datetime(
            product_id, location_ids_tuple, initial_end, inclusive=False
        )

    def _get_opening_balance_qty(self, product_id, location_ids_tuple, date_from):
        self.ensure_one()
        if self.date_from <= self.INITIAL_LOAD_DATE:
            return 0.0
        return self._get_stock_at_datetime(
            product_id, location_ids_tuple, date_from, inclusive=True
        )

    def _get_initial_load_export_rows(self, location_ids):
        self.ensure_one()
        if not self._includes_initial_load():
            return []

        initial_start, initial_end = self._get_initial_load_bounds()
        location_ids_tuple = tuple(location_ids.ids)
        self._cr.execute("""
            SELECT DISTINCT product_id, location_id
            FROM stock_quant
            WHERE location_id IN %(location_ids)s
              AND (
                  (create_date >= %(initial_start)s AND create_date <= %(initial_end)s)
                  OR (in_date >= %(initial_start)s AND in_date <= %(initial_end)s)
              )
        """, {
            "location_ids": location_ids_tuple,
            "initial_start": initial_start,
            "initial_end": initial_end,
        })
        pairs = self._cr.fetchall()
        if not pairs:
            return []

        product_map = {
            product.id: product
            for product in self.env["product.product"].browse(
                list({product_id for product_id, _location_id in pairs})
            )
        }
        location_map = {
            location.id: location
            for location in self.env["stock.location"].browse(
                list({location_id for _product_id, location_id in pairs})
            )
        }

        rows = []
        for product_id, location_id in pairs:
            qty = self._get_stock_at_datetime(
                product_id, (location_id,), initial_end, inclusive=False
            )
            if not qty:
                continue
            product = product_map.get(product_id)
            location = location_map.get(location_id)
            rows.append({
                "date": initial_end,
                "reference": "CARGA INICIAL",
                "origin": "SIN TRAZABILIDAD HISTORICA",
                "product_id": product_id,
                "product_name": product.name if product else "",
                "default_code": product.default_code if product else "",
                "quantity": qty,
                "uom_name": product.uom_id.name if product and product.uom_id else "",
                "location_name": location.complete_name if location else "",
                "state": "done",
            })
        return rows

    def _generate_lines(self):
        """Genera las líneas del reporte"""
        self.ensure_one()

        self.line_ids.unlink()
        self.warehouse_line_ids.unlink()

        location_domain = self._get_location_domain()
        location_ids = self.env["stock.location"].search(location_domain)

        if not location_ids:
            raise UserError(_("No se encontraron ubicaciones para el criterio seleccionado"))

        date_from = datetime.combine(self.date_from, time.min)
        date_to = datetime.combine(self.date_to, time.max)

        # Construir filtro de producto para la consulta SQL
        product_filter_sql = ""
        base_params = {
            "location_ids": tuple(location_ids.ids),
            "date_from": date_from,
            "date_to": date_to,
        }
        if self.product_id:
            product_filter_sql = "AND product_id = %(product_id)s"
            base_params["product_id"] = self.product_id.id

        self._cr.execute("""
            SELECT DISTINCT product_id
            FROM (
                SELECT product_id
                FROM stock_move
                WHERE (location_id IN %(location_ids)s OR location_dest_id IN %(location_ids)s)
                  AND state = 'done'
                  AND date >= %(date_from)s
                  {product_filter}
                UNION
                SELECT product_id
                FROM stock_quant
                WHERE location_id IN %(location_ids)s
                  {product_filter}
            ) AS products
        """.format(product_filter=product_filter_sql), base_params)

        product_ids = [row[0] for row in self._cr.fetchall()]

        if not product_ids:
            return

        products = self.env["product.product"].browse(product_ids)

        lines_to_create = []
        for product in products:
            line_vals = self._get_product_line_vals(product, location_ids, date_from, date_to)
            if line_vals:
                lines_to_create.append(line_vals)

        if lines_to_create:
            self.env["stock.location.report.line"].create(lines_to_create)

        self._generate_warehouse_lines(product_ids, date_from, date_to)

    def _get_product_line_vals(self, product, location_ids, date_from, date_to):
        """Obtiene los valores para una línea de producto"""
        self.ensure_one()

        location_ids_tuple = tuple(location_ids.ids)

        self._cr.execute("""
            SELECT COALESCE(SUM(quantity), 0)
            FROM stock_move
            WHERE product_id = %(product_id)s
              AND location_dest_id IN %(location_ids)s
              AND state = 'done'
              AND date >= %(date_from)s
              AND date <= %(date_to)s
        """, {
            "product_id": product.id,
            "location_ids": location_ids_tuple,
            "date_from": date_from,
            "date_to": date_to,
        })
        entradas = self._cr.fetchone()[0] or 0.0
        carga_inicial = self._get_initial_load_qty(product.id, location_ids_tuple)
        saldo_inicial = self._get_opening_balance_qty(
            product.id, location_ids_tuple, date_from
        )

        self._cr.execute("""
            SELECT COALESCE(SUM(quantity), 0)
            FROM stock_move
            WHERE product_id = %(product_id)s
              AND location_id IN %(location_ids)s
              AND state = 'done'
              AND date >= %(date_from)s
              AND date <= %(date_to)s
        """, {
            "product_id": product.id,
            "location_ids": location_ids_tuple,
            "date_from": date_from,
            "date_to": date_to,
        })
        salidas = self._cr.fetchone()[0] or 0.0

        self._cr.execute("""
            SELECT
                COALESCE(SUM(quantity), 0) as fisico,
                COALESCE(SUM(reserved_quantity), 0) as reservado
            FROM stock_quant
            WHERE product_id = %(product_id)s
              AND location_id IN %(location_ids)s
        """, {
            "product_id": product.id,
            "location_ids": location_ids_tuple,
        })
        result = self._cr.fetchone()
        fisico = result[0] or 0.0
        reservado = result[1] or 0.0

        entradas += carga_inicial

        if (
            saldo_inicial == 0
            and entradas == 0
            and salidas == 0
            and fisico == 0
            and reservado == 0
        ):
            return None

        return {
            "report_id": self.id,
            "product_id": product.id,
            "default_code": product.default_code or "",
            "product_name": product.name,
            "uom_id": product.uom_id.id,
            "saldo_inicial_qty": saldo_inicial,
            "entradas_qty": entradas,
            "salidas_qty": salidas,
            "fisico_qty": fisico,
            "reservado_qty": reservado,
            "disponible_qty": fisico - reservado,
        }

    def _generate_warehouse_lines(self, product_ids, date_from, date_to):
        """Genera el desglose de cantidades por bodega para cada producto"""
        self.ensure_one()
        products = self.env["product.product"].browse(product_ids)
        lines_to_create = []

        for warehouse in self.warehouse_ids:
            # Ubicaciones internas de esta bodega
            wh_locations = self.env["stock.location"].search([
                ("id", "child_of", warehouse.view_location_id.id),
                ("usage", "=", "internal"),
            ])
            # Si hay filtro de ubicación específica, restringir a esa
            if self.location_id:
                if self.location_id.id not in wh_locations.ids:
                    continue
                wh_locations = self.location_id

            if not wh_locations:
                continue

            wh_loc_tuple = tuple(wh_locations.ids)

            for product in products:
                carga_inicial = self._get_initial_load_qty(product.id, wh_loc_tuple)
                saldo_inicial = self._get_opening_balance_qty(
                    product.id, wh_loc_tuple, date_from
                )
                self._cr.execute("""
                    SELECT COALESCE(SUM(quantity), 0)
                    FROM stock_move
                    WHERE product_id = %(pid)s
                      AND location_dest_id IN %(lids)s
                      AND state = 'done'
                      AND date >= %(df)s
                      AND date <= %(dt)s
                """, {"pid": product.id, "lids": wh_loc_tuple, "df": date_from, "dt": date_to})
                entradas = self._cr.fetchone()[0] or 0.0

                self._cr.execute("""
                    SELECT COALESCE(SUM(quantity), 0)
                    FROM stock_move
                    WHERE product_id = %(pid)s
                      AND location_id IN %(lids)s
                      AND state = 'done'
                      AND date >= %(df)s
                      AND date <= %(dt)s
                """, {"pid": product.id, "lids": wh_loc_tuple, "df": date_from, "dt": date_to})
                salidas = self._cr.fetchone()[0] or 0.0

                self._cr.execute("""
                    SELECT
                        COALESCE(SUM(quantity), 0),
                        COALESCE(SUM(reserved_quantity), 0)
                    FROM stock_quant
                    WHERE product_id = %(pid)s
                      AND location_id IN %(lids)s
                """, {"pid": product.id, "lids": wh_loc_tuple})
                result = self._cr.fetchone()
                fisico = result[0] or 0.0
                reservado = result[1] or 0.0

                entradas += carga_inicial

                if (
                    saldo_inicial == 0
                    and entradas == 0
                    and salidas == 0
                    and fisico == 0
                    and reservado == 0
                ):
                    continue

                lines_to_create.append({
                    "report_id": self.id,
                    "product_id": product.id,
                    "default_code": product.default_code or "",
                    "product_name": product.name,
                    "uom_id": product.uom_id.id,
                    "warehouse_id": warehouse.id,
                    "warehouse_name": warehouse.name,
                    "saldo_inicial_qty": saldo_inicial,
                    "entradas_qty": entradas,
                    "salidas_qty": salidas,
                    "fisico_qty": fisico,
                    "reservado_qty": reservado,
                    "disponible_qty": fisico - reservado,
                })

        if lines_to_create:
            self.env["stock.location.report.warehouse.line"].create(lines_to_create)

    def action_export_excel(self):
        """Exporta el reporte a Excel"""
        self.ensure_one()
        if self.state != "generated":
            raise UserError(_("Primero debe generar el reporte"))

        return {
            "type": "ir.actions.act_url",
            "url": "/stock_location_report/export/%s" % self.id,
            "target": "self",
        }
