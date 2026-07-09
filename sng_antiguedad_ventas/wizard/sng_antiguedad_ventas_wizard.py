# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SngAntiguedadVentasWizard(models.TransientModel):
    _name = "sng.antiguedad.ventas.wizard"
    _description = "Wizard Reporte Antigüedad de Ventas"

    cutoff_date = fields.Date(
        string="Fecha de corte",
        required=True,
        default=fields.Date.context_today,
    )
    num_months = fields.Integer(
        string="Meses de antigüedad",
        default=12,
        help="Número de tramos mensuales (1-12) que se mostrarán en el Excel. "
             "En pantalla siempre se pueden activar los 12 tramos.",
    )

    @api.constrains("num_months")
    def _check_num_months(self):
        for rec in self:
            if rec.num_months < 1 or rec.num_months > 12:
                raise ValidationError(
                    _("El número de meses debe estar entre 1 y 12.")
                )

    def action_open_report(self):
        self.ensure_one()
        report_model = self.env["sng.antiguedad.ventas"]
        report_model._rebuild_snapshot(self.cutoff_date, self.num_months)
        return {
            "type": "ir.actions.act_window",
            "name": "Antigüedad de Ventas",
            "res_model": "sng.antiguedad.ventas",
            "view_mode": "list",
            "domain": report_model._get_snapshot_domain(self.cutoff_date),
            "context": {
                "sng_av_cutoff_date": fields.Date.to_string(self.cutoff_date),
                "sng_av_num_months": self.num_months,
                "allowed_company_ids": self.env.context.get(
                    "allowed_company_ids", self.env.companies.ids
                ),
                "create": False,
                "edit": False,
                "delete": False,
            },
        }

    def action_export_xlsx(self):
        self.ensure_one()
        report_model = self.env["sng.antiguedad.ventas"]
        report_model._rebuild_snapshot(self.cutoff_date, self.num_months)
        return report_model._get_xlsx_action(self.cutoff_date, self.num_months)
