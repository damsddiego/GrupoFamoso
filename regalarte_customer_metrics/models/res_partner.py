# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    customer_metric_current_id = fields.Many2one(
        "regalarte.customer.metric",
        string="Metrica actual",
        compute="_compute_customer_metric_current",
        readonly=True,
    )
    customer_metric_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda metricas",
        related="customer_metric_current_id.currency_id",
        readonly=True,
    )
    customer_company_dpp_days = fields.Float(
        string="DPP (dias)",
        related="customer_metric_current_id.customer_dpp_days",
        readonly=True,
    )
    customer_company_current_month_sales = fields.Monetary(
        string="Venta Mes Actual",
        related="customer_metric_current_id.customer_current_month_sales",
        currency_field="customer_metric_currency_id",
        readonly=True,
    )
    customer_company_previous_month_sales = fields.Monetary(
        string="Venta Mes Anterior",
        related="customer_metric_current_id.customer_previous_month_sales",
        currency_field="customer_metric_currency_id",
        readonly=True,
    )
    customer_company_quarterly_avg_sales = fields.Monetary(
        string="Promedio Trimestral",
        related="customer_metric_current_id.customer_quarterly_avg_sales",
        currency_field="customer_metric_currency_id",
        readonly=True,
    )
    customer_company_semiannual_avg_sales = fields.Monetary(
        string="Promedio Semestral",
        related="customer_metric_current_id.customer_semiannual_avg_sales",
        currency_field="customer_metric_currency_id",
        readonly=True,
    )
    customer_company_annual_avg_sales = fields.Monetary(
        string="Promedio Anual",
        related="customer_metric_current_id.customer_annual_avg_sales",
        currency_field="customer_metric_currency_id",
        readonly=True,
    )
    customer_company_monthly_collection_avg = fields.Monetary(
        string="Promedio Cobranza Mensual",
        related="customer_metric_current_id.customer_monthly_collection_avg",
        currency_field="customer_metric_currency_id",
        readonly=True,
    )
    customer_company_quarterly_collection_avg = fields.Monetary(
        string="Promedio Cobranza Trimestral",
        related="customer_metric_current_id.customer_quarterly_collection_avg",
        currency_field="customer_metric_currency_id",
        readonly=True,
    )
    customer_company_metrics_last_update = fields.Datetime(
        string="Ultima actualizacion metricas",
        related="customer_metric_current_id.customer_metrics_last_update",
        readonly=True,
    )

    @api.depends("commercial_partner_id")
    @api.depends_context("company")
    def _compute_customer_metric_current(self):
        commercial_partner_ids = self.commercial_partner_id.ids
        if not commercial_partner_ids:
            self.customer_metric_current_id = False
            return

        metrics = self.env["regalarte.customer.metric"].search(
            [
                ("partner_id", "in", commercial_partner_ids),
                ("company_id", "=", self.env.company.id),
            ]
        )
        metrics_by_partner = {metric.partner_id.id: metric for metric in metrics}
        for partner in self:
            partner.customer_metric_current_id = metrics_by_partner.get(
                partner.commercial_partner_id.id
            )

    def action_recompute_customer_metrics(self):
        self.env["regalarte.customer.metric"].sudo()._recompute_metrics_for_partners(
            self.commercial_partner_id,
            company_ids=self.env.context.get("allowed_company_ids") or self.env.companies.ids,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Metricas actualizadas",
                "message": "Se recalcularon las metricas del cliente seleccionado.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_customer_metrics_dashboard(self):
        action = self.env.ref(
            "regalarte_customer_metrics.action_customer_metrics_dashboard"
        ).read()[0]
        action["domain"] = [
            ("partner_id", "in", self.commercial_partner_id.ids),
            ("company_id", "in", self.env.context.get("allowed_company_ids") or self.env.companies.ids),
        ]
        return action

    def action_export_customer_metrics_xlsx(self):
        return self.env["regalarte.customer.metric"].action_export_metrics_xlsx(
            partner_ids=self.commercial_partner_id.ids,
            company_ids=self.env.context.get("allowed_company_ids") or self.env.companies.ids,
        )
