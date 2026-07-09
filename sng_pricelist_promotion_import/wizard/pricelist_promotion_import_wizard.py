# -*- coding: utf-8 -*-

import base64
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, time
from io import BytesIO

import openpyxl

from odoo import _, fields, models
from odoo.exceptions import UserError


class SngPricelistPromotionImportWizard(models.TransientModel):
    _name = "sng.pricelist.promotion.import.wizard"
    _description = "Importador de promociones a listas de precios"

    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
    )
    file = fields.Binary(
        string="Archivo Excel",
        required=True,
        help="Sube un archivo .xlsx con las columnas Codigo y Precio Remate.",
    )
    filename = fields.Char(string="Nombre del archivo")
    date_start = fields.Date(
        string="Fecha inicial",
        required=True,
        default=fields.Date.context_today,
    )
    date_end = fields.Date(string="Fecha final", required=True)

    @staticmethod
    def _normalize_header(value):
        text = unicodedata.normalize("NFKD", str(value or "").strip())
        text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", text).lower()

    @staticmethod
    def _normalize_code(value):
        if value in (None, ""):
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    @staticmethod
    def _parse_number(value):
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip().replace(" ", "")
        if not text:
            return None

        if "," in text and "." in text:
            if re.match(r"^\d{1,3}(\.\d{3})+,\d+$", text):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".") if text.count(",") == 1 else text.replace(",", "")

        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_error_list(errors, max_items=30):
        if len(errors) <= max_items:
            return "\n".join(errors)
        remaining = len(errors) - max_items
        return "\n".join(errors[:max_items] + [_("... y %s error(es) mas.") % remaining])

    def _get_validity_datetimes(self):
        self.ensure_one()
        if self.date_start > self.date_end:
            raise UserError(_("La fecha final debe ser mayor o igual a la fecha inicial."))
        return (
            datetime.combine(self.date_start, time.min),
            datetime.combine(self.date_end, time.max.replace(microsecond=0)),
        )

    def _load_sheet(self):
        self.ensure_one()
        if not self.filename or not self.filename.lower().endswith(".xlsx"):
            raise UserError(_("El archivo debe estar en formato .xlsx."))
        try:
            workbook = openpyxl.load_workbook(BytesIO(base64.b64decode(self.file)), data_only=True)
        except Exception as error:
            raise UserError(_("No se pudo leer el archivo Excel: %s") % error) from error
        return workbook.active

    def _extract_rows(self, sheet):
        headers = {
            self._normalize_header(cell.value): index
            for index, cell in enumerate(sheet[1])
            if cell.value not in (None, "")
        }

        code_index = headers.get("codigo")
        price_index = headers.get("precio remate")
        if code_index is None or price_index is None:
            detected_headers = " | ".join(headers.keys()) or _("sin encabezados")
            raise UserError(
                _(
                    "Encabezados invalidos. Se requieren las columnas Codigo y Precio Remate. "
                    "Encabezados detectados: %s"
                )
                % detected_headers
            )

        rows_by_code = {}
        errors = []
        duplicated_codes = defaultdict(list)

        for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not row or not any(value not in (None, "") for value in row):
                continue

            code = self._normalize_code(row[code_index] if code_index < len(row) else None)
            price = self._parse_number(row[price_index] if price_index < len(row) else None)

            if not code:
                errors.append(_("Fila %s: falta el codigo del producto.") % row_number)
                continue
            if price is None:
                errors.append(_("Fila %s: el Precio Remate no es numerico para %s.") % (row_number, code))
                continue
            if price < 0:
                errors.append(_("Fila %s: el Precio Remate no puede ser negativo para %s.") % (row_number, code))
                continue

            if code in rows_by_code:
                duplicated_codes[code].append(row_number)
                continue
            rows_by_code[code] = {
                "code": code,
                "price": price,
                "row_number": row_number,
            }

        for code, row_numbers in duplicated_codes.items():
            first_row = rows_by_code[code]["row_number"]
            errors.append(
                _("Codigo %s: esta duplicado en las filas %s.")
                % (code, ", ".join(str(row) for row in [first_row] + row_numbers))
            )

        if errors:
            raise UserError(_("El archivo tiene errores:\n%s") % self._format_error_list(errors))
        if not rows_by_code:
            raise UserError(_("El archivo no contiene lineas validas para importar."))

        return list(rows_by_code.values())

    def _get_products_by_code(self, codes):
        products = self.env["product.product"].search([("default_code", "in", list(codes))])
        products_by_code = defaultdict(lambda: self.env["product.product"])
        for product in products:
            products_by_code[self._normalize_code(product.default_code)] |= product
        return products_by_code

    def _prepare_product_rows(self, imported_rows):
        products_by_code = self._get_products_by_code(row["code"] for row in imported_rows)
        prepared_rows = []
        errors = []
        template_rows = defaultdict(list)

        for row in imported_rows:
            products = products_by_code.get(row["code"], self.env["product.product"])
            if not products:
                errors.append(_("Fila %s: no existe producto con codigo %s.") % (row["row_number"], row["code"]))
                continue
            if len(products) > 1:
                errors.append(
                    _("Fila %s: existe mas de un producto con codigo %s.")
                    % (row["row_number"], row["code"])
                )
                continue

            product = products[0]
            prepared_rows.append({
                **row,
                "product": product,
                "product_tmpl": product.product_tmpl_id,
            })
            template_rows[product.product_tmpl_id.id].append(row)

        for rows in template_rows.values():
            if len(rows) > 1:
                errors.append(
                    _("Producto %s: varios codigos del archivo apuntan al mismo producto: %s.")
                    % (rows[0]["code"], ", ".join(row["code"] for row in rows))
                )

        if errors:
            raise UserError(
                _("No se pudo validar productos usando la referencia interna:\n%s")
                % self._format_error_list(errors)
            )

        return prepared_rows

    def _get_pricelists(self):
        self.ensure_one()
        pricelists = self.env["product.pricelist"].search([
            ("active", "=", True),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", self.company_id.id),
        ])
        if not pricelists:
            raise UserError(_("No hay listas de precios activas para la compania actual."))
        return pricelists

    def _convert_price_for_pricelist(self, amount, pricelist):
        self.ensure_one()
        company = pricelist.company_id or self.company_id
        source_currency = company.currency_id
        target_currency = pricelist.currency_id

        if target_currency == source_currency:
            return amount

        custom_rate = getattr(pricelist, "sng_custom_exchange_rate", 0.0) or 0.0
        if custom_rate > 0:
            return target_currency.round(amount / custom_rate)

        return source_currency._convert(
            amount,
            target_currency,
            company,
            self.date_start,
        )

    def action_import(self):
        self.ensure_one()
        date_start, date_end = self._get_validity_datetimes()
        imported_rows = self._extract_rows(self._load_sheet())
        product_rows = self._prepare_product_rows(imported_rows)
        pricelists = self._get_pricelists()

        item_values = []
        for row in product_rows:
            for pricelist in pricelists:
                item_values.append({
                    "pricelist_id": pricelist.id,
                    "applied_on": "1_product",
                    "product_tmpl_id": row["product_tmpl"].id,
                    "compute_price": "fixed",
                    "fixed_price": self._convert_price_for_pricelist(row["price"], pricelist),
                    "min_quantity": 0.0,
                    "date_start": date_start,
                    "date_end": date_end,
                })

        self.env["product.pricelist.item"].create(item_values)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Importacion completada"),
                "message": _(
                    "Se crearon %(rules)s regla(s) para %(products)s producto(s) en %(pricelists)s lista(s) de precios."
                ) % {
                    "rules": len(item_values),
                    "products": len(product_rows),
                    "pricelists": len(pricelists),
                },
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
