# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SngCxcReportWizard(models.TransientModel):
    _name = "sng.cxc.report.wizard"
    _description = "Wizard Reporte CxC"

    cutoff_date = fields.Date(
        string="Fecha de corte",
        required=True,
        default=fields.Date.context_today,
    )

    @api.model
    def default_get(self, field_list):
        values = super().default_get(field_list)
        if not values.get("cutoff_date"):
            values["cutoff_date"] = fields.Date.context_today(self)
        return values

    def action_open_report(self):
        self.ensure_one()
        report_model = self.env["sng.cxc.report"]
        report_model._rebuild_snapshot(self.cutoff_date)
        action = self.env.ref("sng_cxc_report.action_sng_cxc_report").read()[0]
        action["domain"] = report_model._get_snapshot_domain(self.cutoff_date)
        action["context"] = {
            "search_default_filter_with_balance": 0,
            "search_default_group_by_company": 0,
            "sng_cxc_cutoff_date": fields.Date.to_string(self.cutoff_date),
            "allowed_company_ids": self.env.context.get("allowed_company_ids", self.env.companies.ids),
        }
        return action

    def action_export_xlsx(self):
        self.ensure_one()
        report_model = self.env["sng.cxc.report"]
        report_model._rebuild_snapshot(self.cutoff_date)
        return report_model._get_xlsx_action(self.cutoff_date)
