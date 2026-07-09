# -*- coding: utf-8 -*-
from odoo import api, models


class ReportStockKardex(models.AbstractModel):
    _name = "report.sng_stock_kardex_report.report_stock_kardex"
    _description = "Reporte Kardex de Inventario"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["stock.kardex.wizard"].browse(docids)
        return {
            "doc_ids": docids,
            "doc_model": "stock.kardex.wizard",
            "docs": docs,
            "data": data,
        }
