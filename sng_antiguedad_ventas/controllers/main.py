# -*- coding: utf-8 -*-
import json

from odoo import http
from odoo.http import content_disposition, request
from odoo.tools import html_escape


class SngAntiguedadVentasController(http.Controller):
    @http.route(
        "/sng_antiguedad_ventas/xlsx",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def get_report_xlsx(self, model, options, output_format, report_name, **kwargs):
        uid = request.session.uid
        options = json.loads(options or "{}")
        allowed_company_ids = options.get("allowed_company_ids")
        report_obj = request.env[model].with_user(uid)
        if allowed_company_ids:
            report_obj = report_obj.with_context(
                allowed_company_ids=allowed_company_ids
            )
        token = "sng_antiguedad_ventas_xlsx_token"
        try:
            if output_format == "xlsx":
                response = request.make_response(
                    None,
                    headers=[
                        (
                            "Content-Type",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ),
                        (
                            "Content-Disposition",
                            content_disposition("%s.xlsx" % report_name),
                        ),
                    ],
                )
                report_obj.get_xlsx_report(options, response)
                response.set_cookie("fileToken", token)
                return response
        except Exception as exc:
            error = {
                "code": 200,
                "message": "Odoo Server Error",
                "data": http.serialize_exception(exc),
            }
            return request.make_response(html_escape(json.dumps(error)))

        return request.not_found()
