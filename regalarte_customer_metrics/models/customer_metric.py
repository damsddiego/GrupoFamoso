# -*- coding: utf-8 -*-

import io
import json

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import json_default

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class RegalarteCustomerMetric(models.Model):
    _name = "regalarte.customer.metric"
    _description = "Metrica de Cliente por Compania"
    _order = "customer_dpp_days desc, partner_id"
    _rec_name = "partner_id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente Comercial",
        required=True,
        readonly=True,
        index=True,
        domain=[("is_company", "=", True)],
    )
    partner_name = fields.Char(string="Cliente", readonly=True, index=True)
    salesperson_user_id = fields.Many2one(
        "res.users",
        string="Vendedor Odoo",
        readonly=True,
        index=True,
    )
    salesperson_partner_id = fields.Many2one(
        "res.partner",
        string="Vendedor",
        domain=[("is_salesperson", "=", True)],
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        required=True,
        readonly=True,
    )
    country_id = fields.Many2one(
        "res.country",
        string="Pais",
        readonly=True,
        index=True,
    )
    customer_dpp_days = fields.Float(
        string="DPP (dias)",
        digits=(16, 2),
        readonly=True,
        index=True,
        default=0.0,
    )
    customer_current_month_sales = fields.Monetary(
        string="Venta Mes Actual",
        currency_field="currency_id",
        readonly=True,
        default=0.0,
    )
    customer_previous_month_sales = fields.Monetary(
        string="Venta Mes Anterior",
        currency_field="currency_id",
        readonly=True,
        default=0.0,
    )
    customer_quarterly_avg_sales = fields.Monetary(
        string="Promedio Trimestral",
        currency_field="currency_id",
        readonly=True,
        default=0.0,
    )
    customer_semiannual_avg_sales = fields.Monetary(
        string="Promedio Semestral",
        currency_field="currency_id",
        readonly=True,
        default=0.0,
    )
    customer_annual_avg_sales = fields.Monetary(
        string="Promedio Anual",
        currency_field="currency_id",
        readonly=True,
        default=0.0,
    )
    customer_monthly_collection_avg = fields.Monetary(
        string="Promedio Cobranza Mensual",
        currency_field="currency_id",
        readonly=True,
        default=0.0,
    )
    customer_quarterly_collection_avg = fields.Monetary(
        string="Promedio Cobranza Trimestral",
        currency_field="currency_id",
        readonly=True,
        default=0.0,
    )
    customer_metrics_last_update = fields.Datetime(
        string="Ultima actualizacion",
        readonly=True,
    )

    _sql_constraints = [
        (
            "regalarte_customer_metric_partner_company_uniq",
            "unique(partner_id, company_id)",
            "Ya existe una metrica para este cliente y compania.",
        ),
    ]

    @api.model
    def cron_recompute_customer_metrics(self):
        companies = self.env["res.company"].sudo().search([])
        for company in companies:
            self._recompute_metrics_for_company(company)
        return True

    @api.model
    def action_export_metrics_xlsx(self, partner_ids=None, company_ids=None):
        partner_ids = partner_ids or []
        company_ids = company_ids or self.env.context.get("allowed_company_ids") or self.env.companies.ids
        metrics = self.search(
            [
                ("partner_id", "in", partner_ids),
                ("company_id", "in", company_ids),
            ],
            order="company_id, partner_name",
        )
        if not metrics:
            raise UserError("No hay metricas para exportar con el filtro actual.")
        return {
            "type": "ir.actions.report",
            "data": {
                "model": self._name,
                "options": json.dumps(
                    {"metric_ids": metrics.ids},
                    default=json_default,
                ),
                "output_format": "xlsx",
                "report_name": "metricas_clientes_por_compania",
            },
            "report_type": "regalarte_customer_metrics_xlsx",
        }

    @api.model
    def _recompute_metrics_for_partners(self, commercial_partners, company_ids=None):
        commercial_partners = commercial_partners.with_context(active_test=False).commercial_partner_id.filtered("id")
        company_ids = company_ids or self.env.context.get("allowed_company_ids") or self.env.companies.ids
        companies = self.env["res.company"].sudo().browse(company_ids).exists()
        for company in companies:
            self._recompute_metrics_for_company(company, commercial_partners=commercial_partners)
        return True

    @api.model
    def _recompute_metrics_for_company(self, company, commercial_partners=None):
        if commercial_partners:
            partner_ids = commercial_partners.ids
        else:
            partner_ids = self._get_metric_target_commercial_partner_ids(company)
        if not partner_ids:
            return {}

        partner_model = self.env["res.partner"].with_context(active_test=False)
        partners = partner_model.browse(partner_ids).filtered("id")
        metrics_by_partner = self._get_customer_metrics_by_partner(partners, company)
        salesperson_by_partner = self._get_salesperson_partner_by_partner(partners, company)
        existing_metrics = self.search(
            [("company_id", "=", company.id), ("partner_id", "in", partner_ids)]
        )
        existing_by_partner = {metric.partner_id.id: metric for metric in existing_metrics}
        timestamp = fields.Datetime.now()

        for partner in partners:
            salesperson_partner = salesperson_by_partner.get(partner.id)
            values = dict(
                metrics_by_partner.get(partner.id, self._get_empty_customer_metrics()),
                partner_id=partner.id,
                partner_name=partner.display_name,
                salesperson_user_id=partner.user_id.id,
                salesperson_partner_id=salesperson_partner.id if salesperson_partner else False,
                company_id=company.id,
                currency_id=company.currency_id.id,
                country_id=partner.country_id.id,
                customer_metrics_last_update=timestamp,
            )
            metric = existing_by_partner.get(partner.id)
            if metric:
                metric.write(values)
            else:
                self.create(values)
        return metrics_by_partner

    @api.model
    def _get_salesperson_partner_by_partner(self, partners, company):
        salesperson_by_partner = {
            partner.id: partner.assigned_salesperson_id
            for partner in partners
        }
        missing_partner_ids = [
            partner.id
            for partner in partners
            if not salesperson_by_partner[partner.id]
        ]
        if not missing_partner_ids:
            return salesperson_by_partner

        moves = self.env["account.move"].sudo().search(
            [
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("company_id", "=", company.id),
                ("commercial_partner_id", "in", missing_partner_ids),
                ("salesperson_id", "!=", False),
            ],
            order="invoice_date desc, date desc, id desc",
        )
        for move in moves:
            partner_id = move.commercial_partner_id.id
            if partner_id in missing_partner_ids and not salesperson_by_partner[partner_id]:
                salesperson_by_partner[partner_id] = move.salesperson_id

        return salesperson_by_partner

    @api.model
    def _get_metric_target_commercial_partner_ids(self, company):
        self.env["account.move"].flush_model([
            "commercial_partner_id",
            "company_id",
            "state",
            "move_type",
        ])
        self.env["res.partner"].flush_model([
            "commercial_partner_id",
            "customer_rank",
        ])
        self.env.cr.execute(
            """
                SELECT DISTINCT partner_id
                FROM (
                    SELECT commercial_partner_id AS partner_id
                    FROM res_partner
                    WHERE customer_rank > 0
                      AND commercial_partner_id IS NOT NULL

                    UNION

                    SELECT commercial_partner_id AS partner_id
                    FROM account_move
                    WHERE state = 'posted'
                      AND move_type IN ('out_invoice', 'out_refund')
                      AND company_id = %s
                      AND commercial_partner_id IS NOT NULL
                ) partners
            """,
            (company.id,),
        )
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _get_empty_customer_metrics(self):
        return {
            "customer_dpp_days": 0.0,
            "customer_current_month_sales": 0.0,
            "customer_previous_month_sales": 0.0,
            "customer_quarterly_avg_sales": 0.0,
            "customer_semiannual_avg_sales": 0.0,
            "customer_annual_avg_sales": 0.0,
            "customer_monthly_collection_avg": 0.0,
            "customer_quarterly_collection_avg": 0.0,
        }

    @api.model
    def _get_customer_metrics_by_partner(self, commercial_partners, company):
        commercial_partners = commercial_partners.commercial_partner_id.filtered("id")
        if not commercial_partners:
            return {}

        partner_ids = commercial_partners.ids
        periods = self._get_customer_metric_periods()
        self._flush_metric_models()
        metrics_by_partner = {
            partner_id: self._get_empty_customer_metrics()
            for partner_id in partner_ids
        }

        for partner_id, values in self._get_sales_metrics(partner_ids, periods, company).items():
            metrics_by_partner[partner_id].update(values)

        for partner_id, values in self._get_collection_metrics(partner_ids, periods, company).items():
            metrics_by_partner[partner_id].update(values)

        for partner_id, dpp_days in self._get_dpp_metrics(partner_ids, company).items():
            metrics_by_partner[partner_id]["customer_dpp_days"] = dpp_days

        return metrics_by_partner

    @api.model
    def _get_customer_metric_periods(self):
        today = fields.Date.to_date(fields.Date.context_today(self))
        month_start = today.replace(day=1)
        next_month_start = month_start + relativedelta(months=1)
        return {
            "month_start": month_start,
            "previous_month_start": month_start + relativedelta(months=-1),
            "last_3_months_start": month_start + relativedelta(months=-2),
            "last_6_months_start": month_start + relativedelta(months=-5),
            "last_12_months_start": month_start + relativedelta(months=-11),
            "period_end": next_month_start,
        }

    @api.model
    def _flush_metric_models(self):
        self.env["account.move"].flush_model([
            "state",
            "move_type",
            "commercial_partner_id",
            "company_id",
            "invoice_date",
            "date",
            "amount_total_signed",
            "payment_state",
            "origin_payment_id",
            "statement_line_id",
            "journal_id",
        ])
        self.env["account.move.line"].flush_model(["move_id", "account_id"])
        self.env["account.partial.reconcile"].flush_model([
            "amount",
            "max_date",
            "debit_move_id",
            "credit_move_id",
        ])
        self.env["account.account"].flush_model(["account_type"])
        self.env["account.journal"].flush_model(["type"])

    @api.model
    def _get_sales_metrics(self, partner_ids, periods, company):
        self.env.cr.execute(
            """
                SELECT
                    move.commercial_partner_id AS partner_id,
                    COALESCE(SUM(
                        CASE
                            WHEN COALESCE(move.invoice_date, move.date) >= %s
                             AND COALESCE(move.invoice_date, move.date) < %s
                            THEN move.amount_total_signed
                            ELSE 0
                        END
                    ), 0.0) AS current_month_sales,
                    COALESCE(SUM(
                        CASE
                            WHEN COALESCE(move.invoice_date, move.date) >= %s
                             AND COALESCE(move.invoice_date, move.date) < %s
                            THEN move.amount_total_signed
                            ELSE 0
                        END
                    ), 0.0) AS previous_month_sales,
                    COALESCE(SUM(
                        CASE
                            WHEN COALESCE(move.invoice_date, move.date) >= %s
                             AND COALESCE(move.invoice_date, move.date) < %s
                            THEN move.amount_total_signed
                            ELSE 0
                        END
                    ), 0.0) AS rolling_3_months_sales,
                    COALESCE(SUM(
                        CASE
                            WHEN COALESCE(move.invoice_date, move.date) >= %s
                             AND COALESCE(move.invoice_date, move.date) < %s
                            THEN move.amount_total_signed
                            ELSE 0
                        END
                    ), 0.0) AS rolling_6_months_sales,
                    COALESCE(SUM(
                        CASE
                            WHEN COALESCE(move.invoice_date, move.date) >= %s
                             AND COALESCE(move.invoice_date, move.date) < %s
                            THEN move.amount_total_signed
                            ELSE 0
                        END
                    ), 0.0) AS rolling_12_months_sales
                FROM account_move move
                WHERE move.state = 'posted'
                  AND move.move_type IN ('out_invoice', 'out_refund')
                  AND move.company_id = %s
                  AND move.commercial_partner_id IN %s
                  AND COALESCE(move.invoice_date, move.date) >= %s
                  AND COALESCE(move.invoice_date, move.date) < %s
                GROUP BY move.commercial_partner_id
            """,
            (
                periods["month_start"],
                periods["period_end"],
                periods["previous_month_start"],
                periods["month_start"],
                periods["last_3_months_start"],
                periods["period_end"],
                periods["last_6_months_start"],
                periods["period_end"],
                periods["last_12_months_start"],
                periods["period_end"],
                company.id,
                tuple(partner_ids),
                periods["last_12_months_start"],
                periods["period_end"],
            ),
        )
        return {
            row["partner_id"]: {
                "customer_current_month_sales": row["current_month_sales"] or 0.0,
                "customer_previous_month_sales": row["previous_month_sales"] or 0.0,
                "customer_quarterly_avg_sales": (row["rolling_3_months_sales"] or 0.0) / 3.0,
                "customer_semiannual_avg_sales": (row["rolling_6_months_sales"] or 0.0) / 6.0,
                "customer_annual_avg_sales": (row["rolling_12_months_sales"] or 0.0) / 12.0,
            }
            for row in self.env.cr.dictfetchall()
        }

    @api.model
    def _get_collection_metrics(self, partner_ids, periods, company):
        self.env.cr.execute(
            """
                WITH invoice_lines AS (
                    SELECT
                        move.id AS invoice_id,
                        move.commercial_partner_id AS partner_id,
                        line.id AS line_id
                    FROM account_move move
                    JOIN account_move_line line
                        ON line.move_id = move.id
                    JOIN account_account account
                        ON account.id = line.account_id
                    WHERE move.state = 'posted'
                      AND move.move_type = 'out_invoice'
                      AND move.company_id = %s
                      AND move.commercial_partner_id IN %s
                      AND account.account_type = 'asset_receivable'
                ),
                cash_partials AS (
                    SELECT
                        il.partner_id,
                        part.amount,
                        part.max_date
                    FROM invoice_lines il
                    JOIN account_partial_reconcile part
                        ON part.debit_move_id = il.line_id
                    JOIN account_move_line counterpart_line
                        ON counterpart_line.id = part.credit_move_id
                    JOIN account_move counterpart_move
                        ON counterpart_move.id = counterpart_line.move_id
                    JOIN account_journal counterpart_journal
                        ON counterpart_journal.id = counterpart_move.journal_id
                    WHERE counterpart_move.id != il.invoice_id
                      AND (
                          counterpart_move.origin_payment_id IS NOT NULL
                          OR counterpart_move.statement_line_id IS NOT NULL
                          OR counterpart_journal.type IN ('bank', 'cash')
                      )

                    UNION ALL

                    SELECT
                        il.partner_id,
                        part.amount,
                        part.max_date
                    FROM invoice_lines il
                    JOIN account_partial_reconcile part
                        ON part.credit_move_id = il.line_id
                    JOIN account_move_line counterpart_line
                        ON counterpart_line.id = part.debit_move_id
                    JOIN account_move counterpart_move
                        ON counterpart_move.id = counterpart_line.move_id
                    JOIN account_journal counterpart_journal
                        ON counterpart_journal.id = counterpart_move.journal_id
                    WHERE counterpart_move.id != il.invoice_id
                      AND (
                          counterpart_move.origin_payment_id IS NOT NULL
                          OR counterpart_move.statement_line_id IS NOT NULL
                          OR counterpart_journal.type IN ('bank', 'cash')
                      )
                )
                SELECT
                    partner_id,
                    COALESCE(SUM(
                        CASE
                            WHEN max_date >= %s AND max_date < %s
                            THEN amount
                            ELSE 0
                        END
                    ), 0.0) AS collected_3_months,
                    COALESCE(SUM(
                        CASE
                            WHEN max_date >= %s AND max_date < %s
                            THEN amount
                            ELSE 0
                        END
                    ), 0.0) AS collected_12_months
                FROM cash_partials
                GROUP BY partner_id
            """,
            (
                company.id,
                tuple(partner_ids),
                periods["last_3_months_start"],
                periods["period_end"],
                periods["last_12_months_start"],
                periods["period_end"],
            ),
        )
        return {
            row["partner_id"]: {
                "customer_monthly_collection_avg": (row["collected_3_months"] or 0.0) / 3.0,
                "customer_quarterly_collection_avg": (row["collected_12_months"] or 0.0) / 4.0,
            }
            for row in self.env.cr.dictfetchall()
        }

    @api.model
    def _get_dpp_metrics(self, partner_ids, company):
        self.env.cr.execute(
            """
                WITH invoice_lines AS (
                    SELECT
                        move.id AS invoice_id,
                        move.commercial_partner_id AS partner_id,
                        COALESCE(move.invoice_date, move.date) AS invoice_date,
                        line.id AS line_id
                    FROM account_move move
                    JOIN account_move_line line
                        ON line.move_id = move.id
                    JOIN account_account account
                        ON account.id = line.account_id
                    WHERE move.state = 'posted'
                      AND move.move_type = 'out_invoice'
                      AND move.payment_state = 'paid'
                      AND move.company_id = %s
                      AND move.commercial_partner_id IN %s
                      AND account.account_type = 'asset_receivable'
                ),
                cash_partials AS (
                    SELECT
                        il.invoice_id,
                        il.partner_id,
                        il.invoice_date,
                        part.max_date
                    FROM invoice_lines il
                    JOIN account_partial_reconcile part
                        ON part.debit_move_id = il.line_id
                    JOIN account_move_line counterpart_line
                        ON counterpart_line.id = part.credit_move_id
                    JOIN account_move counterpart_move
                        ON counterpart_move.id = counterpart_line.move_id
                    JOIN account_journal counterpart_journal
                        ON counterpart_journal.id = counterpart_move.journal_id
                    WHERE counterpart_move.id != il.invoice_id
                      AND (
                          counterpart_move.origin_payment_id IS NOT NULL
                          OR counterpart_move.statement_line_id IS NOT NULL
                          OR counterpart_journal.type IN ('bank', 'cash')
                      )

                    UNION ALL

                    SELECT
                        il.invoice_id,
                        il.partner_id,
                        il.invoice_date,
                        part.max_date
                    FROM invoice_lines il
                    JOIN account_partial_reconcile part
                        ON part.credit_move_id = il.line_id
                    JOIN account_move_line counterpart_line
                        ON counterpart_line.id = part.debit_move_id
                    JOIN account_move counterpart_move
                        ON counterpart_move.id = counterpart_line.move_id
                    JOIN account_journal counterpart_journal
                        ON counterpart_journal.id = counterpart_move.journal_id
                    WHERE counterpart_move.id != il.invoice_id
                      AND (
                          counterpart_move.origin_payment_id IS NOT NULL
                          OR counterpart_move.statement_line_id IS NOT NULL
                          OR counterpart_journal.type IN ('bank', 'cash')
                      )
                ),
                settled_invoices AS (
                    SELECT
                        invoice_id,
                        partner_id,
                        invoice_date,
                        MAX(max_date) AS last_cash_date
                    FROM cash_partials
                    GROUP BY invoice_id, partner_id, invoice_date
                )
                SELECT
                    partner_id,
                    COALESCE(AVG((last_cash_date - invoice_date)::float8), 0.0) AS dpp_days
                FROM settled_invoices
                GROUP BY partner_id
            """,
            (
                company.id,
                tuple(partner_ids),
            ),
        )
        return {
            row["partner_id"]: row["dpp_days"] or 0.0
            for row in self.env.cr.dictfetchall()
        }

    @api.model
    def get_xlsx_report(self, options, response):
        metric_ids = options.get("metric_ids") or []
        metrics = self.browse(metric_ids).exists().sorted(
            lambda metric: (metric.company_id.name or "", metric.partner_name or "")
        )
        if not metrics:
            raise UserError("No hay metricas para exportar.")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Metricas Clientes")

        title_format = workbook.add_format(
            {"bold": True, "font_size": 16, "align": "center", "valign": "vcenter"}
        )
        header_format = workbook.add_format(
            {"bold": True, "bg_color": "#D9E2F3", "border": 1, "align": "center"}
        )
        text_format = workbook.add_format({"border": 1})
        amount_format = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
        date_format = workbook.add_format({"border": 1, "num_format": "yyyy-mm-dd hh:mm"})

        columns = [
            ("Compania", 24, lambda m: m.company_id.display_name or "", text_format),
            ("Cliente", 30, lambda m: m.partner_name or "", text_format),
            ("Vendedor", 24, lambda m: m.salesperson_partner_id.display_name or "", text_format),
            ("DPP", 12, lambda m: m.customer_dpp_days, amount_format),
            ("Venta Mes Anterior", 18, lambda m: m.customer_previous_month_sales, amount_format),
            ("Venta Mes Actual", 16, lambda m: m.customer_current_month_sales, amount_format),
            ("Promedio Trimestral", 18, lambda m: m.customer_quarterly_avg_sales, amount_format),
            ("Promedio Semestral", 18, lambda m: m.customer_semiannual_avg_sales, amount_format),
            ("Promedio Anual", 16, lambda m: m.customer_annual_avg_sales, amount_format),
            ("Cobranza Mensual", 18, lambda m: m.customer_monthly_collection_avg, amount_format),
            ("Cobranza Trimestral", 18, lambda m: m.customer_quarterly_collection_avg, amount_format),
            ("Ultima Actualizacion", 22, lambda m: m.customer_metrics_last_update, date_format),
        ]

        sheet.merge_range(0, 0, 0, len(columns) - 1, "Metricas de Clientes por Compania", title_format)
        sheet.write(1, 0, "Fecha exportacion", header_format)
        sheet.write(1, 1, fields.Datetime.now(), date_format)

        for col, (label, width, _getter, _fmt) in enumerate(columns):
            sheet.set_column(col, col, width)
            sheet.write(3, col, label, header_format)

        row = 4
        for metric in metrics:
            for col, (_label, _width, getter, cell_format) in enumerate(columns):
                value = getter(metric)
                if value in (False, None):
                    value = ""
                sheet.write(row, col, value, cell_format)
            row += 1

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
