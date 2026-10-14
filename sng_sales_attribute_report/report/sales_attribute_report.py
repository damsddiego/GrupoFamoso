# -*- coding: utf-8 -*-

import base64

from odoo import api, models
from odoo.tools.misc import file_path


class SngSalesAttributeReport(models.AbstractModel):
    _name = "report.sng_sales_attribute_report.sales_attribute_report_document"
    _table = "sng_sales_attribute_report_pdf"
    _description = "Reporte PDF de facturación por atributos"

    @api.model
    def _asset_data_uri(self, relative_path, mime_type):
        absolute_path = file_path(relative_path)
        with open(absolute_path, "rb") as asset_file:
            encoded = base64.b64encode(asset_file.read()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            "doc_ids": docids,
            "doc_model": "sng.sales.attribute.report.wizard",
            "docs": self.env["sng.sales.attribute.report.wizard"].browse(docids),
            "report_data": (data or {}).get("report_data", {}),
            "brand_assets": {
                "space_regular": self._asset_data_uri(
                    "sng_sales_attribute_report/static/src/fonts/SpaceGrotesk-Regular.ttf",
                    "font/ttf",
                ),
                "space_bold": self._asset_data_uri(
                    "sng_sales_attribute_report/static/src/fonts/SpaceGrotesk-Bold.ttf",
                    "font/ttf",
                ),
                "currency_font": self._asset_data_uri(
                    "sng_sales_attribute_report/static/src/fonts/DejaVuSans.ttf",
                    "font/ttf",
                ),
                "logo": self._asset_data_uri(
                    "sng_sales_attribute_report/static/src/img/sngcloud-logo.png",
                    "image/png",
                ),
            },
        }
