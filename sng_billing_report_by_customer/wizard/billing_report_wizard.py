# -*- coding: utf-8 -*-

import base64
import io
from collections import OrderedDict

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_amount, format_date

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:  # pragma: no cover - validated through the manifest too
    xlsxwriter = None


class SngBillingReportWizard(models.TransientModel):
    _name = "sng.billing.report.wizard"
    _description = "Asistente de reporte de facturación por cliente"
    _rec_name = "name"

    # This field intentionally stays out of the form view.  Keeping the column
    # makes rolling worker reloads safe: workers that loaded version 18.0.1.0.1
    # can still create transient records while older workers parse the view.
    name = fields.Char(
        string="Nombre",
        default=lambda self: _("Reporte de Facturación por Cliente"),
        readonly=True,
    )

    months_back = fields.Integer(
        string="Cantidad de meses",
        required=True,
        default=1,
        help=(
            "Incluye el mes actual. Por ejemplo, 3 toma desde el primer día "
            "de hace dos meses hasta hoy."
        ),
    )
    date_from = fields.Date(
        string="Fecha inicial",
        compute="_compute_date_range",
    )
    date_to = fields.Date(
        string="Fecha final",
        compute="_compute_date_range",
    )
    company_ids = fields.Many2many(
        comodel_name="res.company",
        relation="sng_billing_report_wizard_company_rel",
        column1="wizard_id",
        column2="company_id",
        string="Compañías",
        required=True,
        default=lambda self: self.env.companies.ids,
        help="Solo se pueden usar compañías activas y permitidas para el usuario.",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        domain="[('customer_rank', '>', 0)]",
        help="Déjelo vacío para incluir todos los clientes.",
    )
    minimum_amount = fields.Float(
        string="Monto neto mínimo",
        digits=(16, 2),
        help=(
            "Déjelo vacío o en cero para no aplicar mínimo. En multicompañía, "
            "el mínimo se evalúa en la moneda de cada compañía."
        ),
    )
    line_ids = fields.One2many(
        comodel_name="sng.billing.report.line",
        inverse_name="wizard_id",
        string="Resultados",
        readonly=True,
    )
    show_results = fields.Boolean(default=False)
    excel_file = fields.Binary(string="Archivo Excel", readonly=True, attachment=False)
    excel_filename = fields.Char(string="Nombre del archivo Excel", readonly=True)

    @api.depends("months_back")
    def _compute_date_range(self):
        today = fields.Date.context_today(self)
        for wizard in self:
            month_count = max(wizard.months_back or 1, 1)
            wizard.date_from = today.replace(day=1) - relativedelta(
                months=month_count - 1
            )
            wizard.date_to = today

    @api.constrains("months_back")
    def _check_months_back(self):
        for wizard in self:
            if wizard.months_back < 1 or wizard.months_back > 120:
                raise ValidationError(
                    _("La cantidad de meses debe estar entre 1 y 120.")
                )

    @api.constrains("minimum_amount")
    def _check_minimum_amount(self):
        for wizard in self:
            if wizard.minimum_amount < 0:
                raise ValidationError(_("El monto mínimo no puede ser negativo."))

    @api.onchange("months_back", "company_ids", "partner_id", "minimum_amount")
    def _onchange_filters(self):
        self.show_results = False
        self.line_ids = [Command.clear()]

    def _get_selected_companies(self):
        self.ensure_one()
        companies = self.company_ids & self.env.companies
        if not companies:
            raise UserError(
                _("Seleccione al menos una compañía permitida para su usuario.")
            )
        return companies

    def _get_invoice_domain(self):
        self.ensure_one()
        companies = self._get_selected_companies()
        domain = [
            ("company_id", "in", companies.ids),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_invoice", "out_refund")),
        ]
        if self.partner_id:
            domain.append(
                (
                    "commercial_partner_id",
                    "=",
                    self.partner_id.commercial_partner_id.id,
                )
            )
        return domain

    def _get_summary_rows(self):
        """Aggregate posted invoices and refunds in each company's currency."""
        self.ensure_one()
        grouped = self.env["account.move"]._read_group(
            domain=self._get_invoice_domain(),
            groupby=["company_id", "commercial_partner_id", "move_type"],
            aggregates=[
                "__count",
                "amount_untaxed_signed:sum",
                "amount_tax_signed:sum",
                "amount_total_signed:sum",
            ],
        )

        summaries = {}
        for (
            company,
            partner,
            move_type,
            document_count,
            amount_untaxed,
            amount_tax,
            amount_total,
        ) in grouped:
            if not company or not partner:
                continue
            key = (company.id, partner.id)
            row = summaries.setdefault(
                key,
                {
                    "company": company,
                    "partner": partner,
                    "invoice_count": 0,
                    "credit_note_count": 0,
                    "amount_untaxed": 0.0,
                    "amount_tax": 0.0,
                    "amount_total": 0.0,
                },
            )
            if move_type == "out_invoice":
                row["invoice_count"] += document_count
            else:
                row["credit_note_count"] += document_count
            row["amount_untaxed"] += amount_untaxed
            row["amount_tax"] += amount_tax
            row["amount_total"] += amount_total

        rows = list(summaries.values())
        if self.minimum_amount:
            rows = [
                row
                for row in rows
                if row["amount_total"] >= self.minimum_amount
            ]

        return sorted(
            rows,
            key=lambda row: (
                row["company"].name.casefold(),
                -row["amount_total"],
                row["partner"].name.casefold(),
            ),
        )

    def _get_report_data(self):
        self.ensure_one()
        rows = self._get_summary_rows()
        if not rows:
            raise UserError(_("No se encontraron datos con los filtros seleccionados."))

        groups = OrderedDict()
        for row in rows:
            company = row["company"]
            currency = company.currency_id
            group = groups.setdefault(
                company.id,
                {
                    "company_id": company.id,
                    "company_name": company.name,
                    "currency_name": currency.name,
                    "currency_symbol": currency.symbol or currency.name,
                    "lines": [],
                    "invoice_count": 0,
                    "credit_note_count": 0,
                    "amount_untaxed": 0.0,
                    "amount_tax": 0.0,
                    "amount_total": 0.0,
                },
            )
            line = {
                "partner_name": row["partner"].display_name,
                "partner_vat": row["partner"].vat or "",
                "invoice_count": row["invoice_count"],
                "credit_note_count": row["credit_note_count"],
                "amount_untaxed": row["amount_untaxed"],
                "amount_tax": row["amount_tax"],
                "amount_total": row["amount_total"],
                "amount_untaxed_display": format_amount(
                    self.env, row["amount_untaxed"], currency
                ),
                "amount_tax_display": format_amount(
                    self.env, row["amount_tax"], currency
                ),
                "amount_total_display": format_amount(
                    self.env, row["amount_total"], currency
                ),
            }
            group["lines"].append(line)
            group["invoice_count"] += row["invoice_count"]
            group["credit_note_count"] += row["credit_note_count"]
            group["amount_untaxed"] += row["amount_untaxed"]
            group["amount_tax"] += row["amount_tax"]
            group["amount_total"] += row["amount_total"]

        for group in groups.values():
            currency = self.env["res.company"].browse(
                group["company_id"]
            ).currency_id
            group["amount_untaxed_display"] = format_amount(
                self.env, group["amount_untaxed"], currency
            )
            group["amount_tax_display"] = format_amount(
                self.env, group["amount_tax"], currency
            )
            group["amount_total_display"] = format_amount(
                self.env, group["amount_total"], currency
            )

        companies = self._get_selected_companies()
        return {
            "date_from": fields.Date.to_string(self.date_from),
            "date_to": fields.Date.to_string(self.date_to),
            "date_from_display": format_date(self.env, self.date_from),
            "date_to_display": format_date(self.env, self.date_to),
            "months_back": self.months_back,
            "partner_name": self.partner_id.display_name if self.partner_id else _("Todos"),
            "minimum_amount": self.minimum_amount,
            "minimum_amount_display": (
                f"{self.minimum_amount:,.2f}" if self.minimum_amount else _("Sin mínimo")
            ),
            "company_names": ", ".join(companies.mapped("name")),
            "groups": list(groups.values()),
            "customer_count": len(rows),
        }

    def action_view_on_screen(self):
        self.ensure_one()
        rows = self._get_summary_rows()
        if not rows:
            raise UserError(_("No se encontraron datos con los filtros seleccionados."))

        commands = [Command.clear()]
        for row in rows:
            commands.append(
                Command.create(
                    {
                        "company_id": row["company"].id,
                        "currency_id": row["company"].currency_id.id,
                        "partner_id": row["partner"].id,
                        "partner_vat": row["partner"].vat or False,
                        "invoice_count": row["invoice_count"],
                        "credit_note_count": row["credit_note_count"],
                        "amount_untaxed": row["amount_untaxed"],
                        "amount_tax": row["amount_tax"],
                        "amount_total": row["amount_total"],
                    }
                )
            )
        self.write({"line_ids": commands, "show_results": True})
        return {
            "type": "ir.actions.act_window",
            "name": _("Reporte de Facturación por Cliente"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref(
                "sng_billing_report_by_customer.view_billing_report_wizard_form"
            ).id,
            "target": "current",
        }

    def action_print_pdf(self):
        self.ensure_one()
        data = self._get_report_data()
        return self.env.ref(
            "sng_billing_report_by_customer.action_billing_report_pdf"
        ).report_action(self, data=data)

    def action_print_excel(self):
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(
                _("La librería Python 'xlsxwriter' es necesaria para generar Excel.")
            )

        data = self._get_report_data()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet(_("Facturación por cliente")[:31])
        worksheet.freeze_panes(5, 0)
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)

        title_format = workbook.add_format(
            {"bold": True, "font_size": 16, "align": "center"}
        )
        subtitle_format = workbook.add_format(
            {"font_size": 10, "align": "center", "font_color": "#555555"}
        )
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#4472C4",
                "font_color": "#FFFFFF",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )
        company_format = workbook.add_format(
            {"bold": True, "bg_color": "#D9E2F3", "border": 1}
        )
        text_format = workbook.add_format({"border": 1})
        center_format = workbook.add_format({"border": 1, "align": "center"})
        amount_format = workbook.add_format(
            {"border": 1, "num_format": "#,##0.00;[Red]-#,##0.00"}
        )
        total_label_format = workbook.add_format(
            {"bold": True, "bg_color": "#E2EFDA", "border": 1, "align": "right"}
        )
        total_amount_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#E2EFDA",
                "border": 1,
                "num_format": "#,##0.00;[Red]-#,##0.00",
            }
        )

        widths = [30, 18, 14, 14, 16, 16, 16, 12]
        for column, width in enumerate(widths):
            worksheet.set_column(column, column, width)

        row_index = 0
        worksheet.merge_range(
            row_index,
            0,
            row_index,
            7,
            _("Reporte de Facturación por Cliente"),
            title_format,
        )
        row_index += 1
        worksheet.merge_range(
            row_index,
            0,
            row_index,
            7,
            _("Período: %(start)s al %(end)s", start=data["date_from_display"], end=data["date_to_display"]),
            subtitle_format,
        )
        row_index += 1
        worksheet.merge_range(
            row_index,
            0,
            row_index,
            7,
            _(
                "Cliente: %(customer)s | Monto mínimo: %(minimum)s",
                customer=data["partner_name"],
                minimum=data["minimum_amount_display"],
            ),
            subtitle_format,
        )
        row_index += 2

        headers = [
            _("Cliente"),
            _("Identificación"),
            _("Facturas"),
            _("Notas de crédito"),
            _("Subtotal neto"),
            _("Impuestos netos"),
            _("Total neto"),
            _("Moneda"),
        ]
        for column, header in enumerate(headers):
            worksheet.write(row_index, column, header, header_format)
        row_index += 1

        for group in data["groups"]:
            worksheet.merge_range(
                row_index,
                0,
                row_index,
                7,
                _(
                    "Compañía: %(company)s (%(currency)s)",
                    company=group["company_name"],
                    currency=group["currency_name"],
                ),
                company_format,
            )
            row_index += 1
            for line in group["lines"]:
                worksheet.write(row_index, 0, line["partner_name"], text_format)
                worksheet.write(row_index, 1, line["partner_vat"], text_format)
                worksheet.write_number(row_index, 2, line["invoice_count"], center_format)
                worksheet.write_number(row_index, 3, line["credit_note_count"], center_format)
                worksheet.write_number(row_index, 4, line["amount_untaxed"], amount_format)
                worksheet.write_number(row_index, 5, line["amount_tax"], amount_format)
                worksheet.write_number(row_index, 6, line["amount_total"], amount_format)
                worksheet.write(row_index, 7, group["currency_name"], center_format)
                row_index += 1

            worksheet.merge_range(
                row_index,
                0,
                row_index,
                1,
                _("Total %(company)s", company=group["company_name"]),
                total_label_format,
            )
            worksheet.write_number(row_index, 2, group["invoice_count"], total_amount_format)
            worksheet.write_number(row_index, 3, group["credit_note_count"], total_amount_format)
            worksheet.write_number(row_index, 4, group["amount_untaxed"], total_amount_format)
            worksheet.write_number(row_index, 5, group["amount_tax"], total_amount_format)
            worksheet.write_number(row_index, 6, group["amount_total"], total_amount_format)
            worksheet.write(row_index, 7, group["currency_name"], total_label_format)
            row_index += 2

        workbook.close()
        output.seek(0)
        filename = "facturacion_por_cliente_%s_%s.xlsx" % (
            data["date_from"],
            data["date_to"],
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
                f"/web/content/{self._name}/{self.id}/excel_file/"
                f"{filename}?download=true"
            ),
            "target": "new",
        }


class SngBillingReportLine(models.TransientModel):
    _name = "sng.billing.report.line"
    _description = "Línea de reporte de facturación por cliente"
    _order = "company_id, amount_total desc, partner_id"

    wizard_id = fields.Many2one(
        comodel_name="sng.billing.report.wizard",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    partner_vat = fields.Char(string="Identificación", readonly=True)
    invoice_count = fields.Integer(string="Facturas", readonly=True)
    credit_note_count = fields.Integer(string="Notas de crédito", readonly=True)
    amount_untaxed = fields.Monetary(
        string="Subtotal neto", currency_field="currency_id", readonly=True
    )
    amount_tax = fields.Monetary(
        string="Impuestos netos", currency_field="currency_id", readonly=True
    )
    amount_total = fields.Monetary(
        string="Total neto", currency_field="currency_id", readonly=True
    )

    def action_open_invoices(self):
        self.ensure_one()
        domain = self.wizard_id._get_invoice_domain() + [
            ("company_id", "=", self.company_id.id),
            ("commercial_partner_id", "=", self.partner_id.id),
        ]
        return {
            "type": "ir.actions.act_window",
            "name": _("Documentos de %(customer)s", customer=self.partner_id.display_name),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": domain,
            "context": {
                "allowed_company_ids": self.wizard_id._get_selected_companies().ids,
            },
            "target": "current",
        }
