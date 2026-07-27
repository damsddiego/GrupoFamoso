# -*- coding: utf-8 -*-

from odoo import api, models


class SngBillingReport(models.AbstractModel):
    _name = (
        "report.sng_billing_report_by_customer.billing_report_document"
    )
    _description = "Reporte PDF de facturación por cliente"

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            "doc_ids": docids,
            "doc_model": "sng.billing.report.wizard",
            "docs": self.env["sng.billing.report.wizard"].browse(docids),
            "data": data or {},
            "company": self.env.company,
        }
