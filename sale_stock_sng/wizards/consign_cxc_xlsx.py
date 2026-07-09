# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.tools import date_utils
from datetime import datetime, time as dt_time


class ConsignCxcXlsx(models.AbstractModel):
    _name = "report.sale_stock_sng.consign_cxc_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "XLSX - Reporte Consignaciones y CxC"

    # =========================
    #   HELPERS: multicompañía
    # =========================
    def _company_ids(self):
        """Compañías permitidas en el contexto actual (selector multicompañía)."""
        return self.env.companies.ids

    def _company_domain(self, include_false=False):
        """
        Dominio para restringir registros a las compañías permitidas.
        - include_false=True permite además registros compartidos (company_id vacío),
          típico de res.partner.
        """
        company_ids = self._company_ids()
        if include_false:
            return ["|", ("company_id", "=", False), ("company_id", "in", company_ids)]
        return [("company_id", "in", company_ids)]

    # =========================
    #   HELPERS: ubicaciones
    # =========================
    def _partner_root_location(self, partner):
        """
        Raíz bodega del cliente:
        1) partner.sale_location_id si existe
        2) property_stock_customer
        """
        loc = getattr(partner, "sale_location_id", False)
        if loc:
            return loc
        loc = getattr(partner, "property_stock_customer", False)
        if loc:
            return loc
        return None

    def _location_allowed_by_wizard(self, root_loc, wiz_locations):
        """
        Si wizard.location_ids está vacío => permitido.
        Si hay location_ids => root_loc debe intersectar (child_of) con esas bodegas.
        """
        if not root_loc:
            return False
        if not wiz_locations:
            return True

        return bool(self.env["stock.location"].sudo().search_count([
            ("id", "=", root_loc.id),
            ("id", "child_of", wiz_locations.ids),
        ]))

    # =========================
    #   HELPERS: stock / valor
    # =========================
    def _valued_stock_now(self, partner, wiz_locations=None):
        """
        Valor actual del stock en la bodega del cliente.
        - Quants en child_of root_loc
        - Intersección con wizard.location_ids si existe
        """
        root = self._partner_root_location(partner)
        if not root:
            return 0.0
        if not self._location_allowed_by_wizard(root, wiz_locations):
            return 0.0

        domain = [("location_id", "child_of", root.id)]
        if wiz_locations:
            # Intersección real (AND)
            domain += [("location_id", "child_of", wiz_locations.ids)]
        domain += self._company_domain()

        quants = self.env["stock.quant"].sudo().with_context(active_test=False).search(domain)

        total = 0.0
        for q in quants:
            total += (q.quantity or 0.0) * (q.product_id.standard_price or 0.0)
        return total

    def _last_movement_date_in_partner_location(self, partner, lower_dt, upper_dt, wiz_locations=None):
        """
        U/Traslado = último movimiento DONE que toque la bodega del cliente:
        - stock.move.line con date <= upper_dt
        - donde location_id o location_dest_id cae en child_of root
        """
        root = self._partner_root_location(partner)
        if not root:
            return False
        if not self._location_allowed_by_wizard(root, wiz_locations):
            return False

        domain = [("state", "=", "done"), ("date", "<=", upper_dt)]
        if lower_dt:
            domain.append(("date", ">=", lower_dt))
        domain += [
            "|",
            ("location_id", "child_of", root.id),
            ("location_dest_id", "child_of", root.id),
        ]

        if wiz_locations:
            domain = ["&"] + domain + [
                "|",
                ("location_id", "child_of", wiz_locations.ids),
                ("location_dest_id", "child_of", wiz_locations.ids),
            ]
        domain += self._company_domain()

        ml = self.env["stock.move.line"].sudo().search(domain, order="date desc, id desc", limit=1)
        return ml.date if ml else False

    # =========================
    #   HELPERS: ventas / cxc
    # =========================
    def _last_sale_or_refund_date(self, partner, lower_d, upper_d):
        """
        Última venta o NTC = último account.move posteado (out_invoice / out_refund)
        """
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("partner_id", "=", partner.id),
            ("invoice_date", "<=", upper_d),
        ]
        if lower_d:
            domain.append(("invoice_date", ">=", lower_d))
        domain += self._company_domain()

        inv = self.env["account.move"].sudo().search(
            domain,
            order="invoice_date desc, id desc",
            limit=1,
        )
        return inv.invoice_date if inv else False

    def _partner_pending_balance(self, partner, lower_d, upper_d):
        """
        Saldo pendiente (CxC) = sum(amount_residual_signed) de facturas/NTC posteadas
        """
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("partner_id", "=", partner.id),
            ("invoice_date", "<=", upper_d),
        ]
        if lower_d:
            domain.append(("invoice_date", ">=", lower_d))
        domain += self._company_domain()

        rows = self.env["account.move"].sudo().search_read(
            domain,
            ["amount_residual_signed"],
        )
        return sum(r.get("amount_residual_signed", 0.0) for r in rows)

    def _partner_credit_limit(self, partner):
        """
        Límite de crédito (campos comunes; ajusta a tu BD si aplica)
        """
        for fname in ("credit_limit", "x_credit_limit", "property_credit_limit"):
            if fname in partner._fields:
                try:
                    return float(getattr(partner, fname) or 0.0)
                except Exception:
                    return 0.0
        return 0.0

    def _partner_fpp_trimestral(self, partner):
        """
        FPP trimestral: mostramos el término de pago (nombre)
        """
        term = getattr(partner, "property_payment_term_id", False)
        return term.name if term else ""

    # =========================
    #   HELPERS: fecha mínima
    # =========================
    def _detect_min_date(self, partners):
        """
        Detecta la primera fecha real (inventario o factura) de esos partners.
        """
        min_dates = []

        pick = self.env["stock.picking"].sudo().search(
            [
                ("partner_id", "in", partners.ids),
                ("state", "=", "done"),
            ] + self._company_domain(),
            order="date_done asc, id asc",
            limit=1,
        )
        if pick and pick.date_done:
            min_dates.append(pick.date_done.date())

        inv = self.env["account.move"].sudo().search(
            [
                ("partner_id", "in", partners.ids),
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_refund")),
            ] + self._company_domain(),
            order="invoice_date asc, id asc",
            limit=1,
        )
        if inv and inv.invoice_date:
            min_dates.append(inv.invoice_date)

        return min(min_dates) if min_dates else False

    # =========================
    #   HELPERS: moneda
    # =========================
    def _safe_ref(self, xmlid):
        try:
            return self.env.ref(xmlid)
        except Exception:
            return False

    def _convert(self, amount, from_currency, to_currency, conv_date):
        if not to_currency or not from_currency:
            return amount
        if from_currency == to_currency:
            return amount
        return from_currency._convert(amount, to_currency, self.env.company, conv_date)

    # =========================
    #        XLSX
    # =========================
    def generate_xlsx_report(self, workbook, data, wizards):
        date_fmt = workbook.add_format({"num_format": "dd/mm/yyyy"})
        dt_fmt = workbook.add_format({"num_format": "dd/mm/yyyy hh:mm:ss"})
        bold = workbook.add_format({"bold": True})
        wrap = workbook.add_format({"text_wrap": True})
        title = workbook.add_format({"bold": True, "font_size": 12})
        h2 = workbook.add_format({"bold": True, "bg_color": "#DDDDDD"})

        money_crc = workbook.add_format({"num_format": "#,##0"})       # colones sin decimales
        money_usd = workbook.add_format({"num_format": "#,##0.00"})    # dólares con 2 decimales

        for wiz in wizards:
            ws = workbook.add_worksheet(_("Consignaciones y CxC"))
            row = 0

            # Partners base
            partner_domain = [("customer_rank", ">", 0), ("active", "=", True)]
            if wiz.user_id:
                partner_domain.append(("user_id", "=", wiz.user_id.id))
            if wiz.location_ids:
                partner_domain += ["|",
                    ("sale_location_id", "in", wiz.location_ids.ids),
                    ("property_stock_customer", "in", wiz.location_ids.ids),
                ]
            # Multicompañía: clientes de las compañías permitidas + compartidos
            partner_domain += self._company_domain(include_false=True)

            partners = self.env["res.partner"].sudo().search(partner_domain)

            # Fecha hasta
            date_to = wiz.date_to
            date_to_dt = date_utils.end_of(date_to, "day")

            # Fecha desde: si no viene en el wizard, solo se usa para mostrar
            # el primer dato detectado; no se limita el rango inferior.
            query_date_from = wiz.date_from
            query_date_from_dt = date_utils.start_of(query_date_from, "day") if query_date_from else False
            display_date_from = query_date_from
            if not display_date_from:
                detected = self._detect_min_date(partners)
                display_date_from = detected or date_to

            # Monedas objetivo
            company_currency = self.env.company.currency_id
            currency_crc = self._safe_ref("base.CRC")  # Colones
            currency_usd = self._safe_ref("base.USD")  # Dólares

            # =========================
            # HEADER
            # =========================
            ws.write(row, 0, _("REPORTE DE BODEGAS DE CONSIGNACIONES DE CLIENTES"), title)
            row += 1
            ws.write(row, 0, _("FECHA Y HORA : "))
            ws.write_datetime(row, 1, datetime.now(), dt_fmt)
            row += 1
            ws.write(row, 0, _("UTIMO MOVIMIENTO DE VENTA Y TRASLADO POR BODEGA Y VALOR DEL INVENTARIO"), h2)
            row += 2

            # Filtros
            ws.write(row, 0, _("Fecha desde"))
            ws.write_datetime(row, 1, datetime.combine(display_date_from, dt_time.min), date_fmt)
            row += 1
            ws.write(row, 0, _("Fecha hasta"))
            ws.write_datetime(row, 1, datetime.combine(date_to, dt_time.min), date_fmt)
            row += 1
            ws.write(row, 0, _("Vendedor"))
            ws.write(row, 1, wiz.user_id.name if wiz.user_id else _("Todos"))
            row += 1
            ws.write(row, 0, _("Bodegas"))
            ws.write(row, 1, ", ".join(wiz.location_ids.mapped("complete_name")) if wiz.location_ids else _("Todas"))
            row += 2

            # =========================
            # ENCABEZADOS TABLA (nuevo + moneda)
            # =========================
            headers = [
                _("Cod cliente"),
                _("Cliente"),
                _("Bodega cliente"),
                _("Vendedor"),
                _("RUTA/ZONA"),
                _("Último traslado Bodega cliente"),
                _("Última venta o NTC"),

                _("Consignado Colones [1]"),
                _("Consignado Dólares [9]"),

                _("CXC Colones"),
                _("CXC Dólares"),

                _("GENERAL Colones"),
                _("GENERAL Dólares"),

                _("Límite de crédito"),
                _("Saldo pendiente"),
                _("FPP trimestral"),
            ]

            for col, h in enumerate(headers):
                ws.write(row, col, h, bold)
            header_row = row
            row += 1

            # =========================
            # TOTALES por moneda
            # =========================
            tot_consign_crc = tot_consign_usd = 0.0
            tot_cxc_crc = tot_cxc_usd = 0.0
            tot_gen_crc = tot_gen_usd = 0.0

            # =========================
            # DATA
            # =========================
            for p in partners:
                root = self._partner_root_location(p)
                if not root:
                    continue
                if not self._location_allowed_by_wizard(root, wiz.location_ids):
                    continue

                last_move_dt = self._last_movement_date_in_partner_location(
                    p, query_date_from_dt, date_to_dt, wiz.location_ids
                )
                last_sale_d = self._last_sale_or_refund_date(p, query_date_from, date_to)

                consign_company = self._valued_stock_now(p, wiz.location_ids)
                pendiente_company = self._partner_pending_balance(p, query_date_from, date_to)
                general_company = (consign_company or 0.0) + (pendiente_company or 0.0)

                # Convertir por fecha (date_to)
                consign_crc = self._convert(consign_company, company_currency, currency_crc, date_to) if currency_crc else consign_company
                consign_usd = self._convert(consign_company, company_currency, currency_usd, date_to) if currency_usd else 0.0

                cxc_crc = self._convert(pendiente_company, company_currency, currency_crc, date_to) if currency_crc else pendiente_company
                cxc_usd = self._convert(pendiente_company, company_currency, currency_usd, date_to) if currency_usd else 0.0

                gen_crc = self._convert(general_company, company_currency, currency_crc, date_to) if currency_crc else general_company
                gen_usd = self._convert(general_company, company_currency, currency_usd, date_to) if currency_usd else 0.0

                credit_limit = self._partner_credit_limit(p)
                fpp = self._partner_fpp_trimestral(p)

                if not consign_company and not pendiente_company and not last_move_dt and not last_sale_d:
                    continue

                code = getattr(p, "client_code", False) or p.vat or str(p.id)
                cliente = p.name or ""
                bodega = root.complete_name if root else ""

                vendedor = p.user_id.name or ""
                zona = p.team_id.name if getattr(p, "team_id", False) else ""

                col = 0
                ws.write(row, col, code); col += 1
                ws.write(row, col, cliente, wrap); col += 1
                ws.write(row, col, bodega, wrap); col += 1
                ws.write(row, col, vendedor); col += 1
                ws.write(row, col, zona); col += 1

                if last_move_dt:
                    ws.write_datetime(row, col, last_move_dt, date_fmt)
                else:
                    ws.write(row, col, "")
                col += 1

                if last_sale_d:
                    ws.write_datetime(row, col, datetime.combine(last_sale_d, dt_time.min), date_fmt)
                else:
                    ws.write(row, col, "")
                col += 1

                # Consignado
                ws.write_number(row, col, consign_crc or 0.0, money_crc); col += 1
                ws.write_number(row, col, consign_usd or 0.0, money_usd); col += 1

                # CXC
                ws.write_number(row, col, cxc_crc or 0.0, money_crc); col += 1
                ws.write_number(row, col, cxc_usd or 0.0, money_usd); col += 1

                # General
                ws.write_number(row, col, gen_crc or 0.0, money_crc); col += 1
                ws.write_number(row, col, gen_usd or 0.0, money_usd); col += 1

                # Extras solicitados
                ws.write_number(row, col, credit_limit or 0.0, money_crc); col += 1
                ws.write_number(row, col, pendiente_company or 0.0, money_crc); col += 1
                ws.write(row, col, fpp or ""); col += 1

                row += 1

                # Totales
                tot_consign_crc += consign_crc or 0.0
                tot_consign_usd += consign_usd or 0.0
                tot_cxc_crc += cxc_crc or 0.0
                tot_cxc_usd += cxc_usd or 0.0
                tot_gen_crc += gen_crc or 0.0
                tot_gen_usd += gen_usd or 0.0

            # =========================
            # TOTALES (por moneda)
            # =========================
            ws.write(row, 0, _("TOTALES"), bold)
            # Consignado
            ws.write_number(row, 7, tot_consign_crc, money_crc)
            ws.write_number(row, 8, tot_consign_usd, money_usd)
            # CXC
            ws.write_number(row, 9, tot_cxc_crc, money_crc)
            ws.write_number(row, 10, tot_cxc_usd, money_usd)
            # General
            ws.write_number(row, 11, tot_gen_crc, money_crc)
            ws.write_number(row, 12, tot_gen_usd, money_usd)
            row += 1

            # =========================
            # PRESENTACIÓN
            # =========================
            widths = [
                12,  # Cod
                35,  # Cliente
                40,  # Bodega
                18,  # Vendedor
                18,  # Zona
                26,  # U traslado
                18,  # Ult venta/ntc
                18,  # Cons CRC
                18,  # Cons USD
                14,  # CXC CRC
                14,  # CXC USD
                16,  # GEN CRC
                16,  # GEN USD
                18,  # Limite crédito
                18,  # Saldo pendiente (company)
                20,  # FPP
            ]
            for i, w in enumerate(widths):
                ws.set_column(i, i, w)

            ws.freeze_panes(header_row + 1, 0)
            ws.autofilter(header_row, 0, row - 1, len(headers) - 1)
