# -*- coding: utf-8 -*-

from odoo import models


class AgedReceivableCustomHandler(models.AbstractModel):
    _inherit = "account.aged.receivable.report.handler"

    def _get_partner_route_report_values(self, partner_ids):
        partners = self.env["res.partner"].browse(partner_ids).exists()
        return {
            partner.id: {
                "unique_id": partner.unique_id or "",
                "sales_route": partner.sales_route_id.display_name or "",
                "salesperson_name": partner.assigned_salesperson_id.display_name or "",
            }
            for partner in partners
        }

    def _blank_partner_route_report_values(self):
        return {
            "unique_id": "",
            "sales_route": "",
            "salesperson_name": "",
        }

    def _add_partner_route_values_to_result(self, result, partner_values):
        result.update(partner_values or self._blank_partner_route_report_values())
        return result

    def _aged_partner_report_custom_engine_common(
        self,
        options,
        internal_type,
        current_groupby,
        next_groupby,
        offset=0,
        limit=None,
    ):
        result = super()._aged_partner_report_custom_engine_common(
            options,
            internal_type,
            current_groupby,
            next_groupby,
            offset=offset,
            limit=limit,
        )

        if not current_groupby:
            return self._add_partner_route_values_to_result(
                result,
                self._blank_partner_route_report_values(),
            )

        if not isinstance(result, list):
            return result

        partner_ids = set()
        for grouping_key, values in result:
            if current_groupby == "partner_id" and grouping_key:
                partner_ids.add(grouping_key)
            elif current_groupby == "id" and values.get("partner_id"):
                partner_ids.add(values["partner_id"])

        values_by_partner = self._get_partner_route_report_values(partner_ids)

        for grouping_key, values in result:
            partner_id = values.get("partner_id") if current_groupby == "id" else grouping_key
            self._add_partner_route_values_to_result(
                values,
                values_by_partner.get(partner_id),
            )

        return result

    def _prepare_partner_values(self):
        values = super()._prepare_partner_values()
        values.update(self._blank_partner_route_report_values())
        return values
