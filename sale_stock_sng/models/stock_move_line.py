# -*- coding: utf-8 -*-
from odoo import models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_aggregated_product_quantities(self, **kwargs):
        aggregated_move_lines = super()._get_aggregated_product_quantities(**kwargs)

        for line_key, line_vals in aggregated_move_lines.items():
            matching_lines = self.filtered(
                lambda ml: self._get_aggregated_properties(move_line=ml)["line_key"] == line_key
            )
            subtotal = sum((ml.quantity or 0.0) * (ml.move_id.price_unit or 0.0) for ml in matching_lines)
            qty = line_vals.get("quantity") or line_vals.get("qty_ordered") or 0.0
            line_vals["subtotal"] = subtotal
            line_vals["price_unit"] = subtotal / qty if qty else 0.0

        return aggregated_move_lines
