# -*- coding: utf-8 -*-
from odoo import models


class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def _prepare_picking_default_values_based_on(self, picking):
        vals = super()._prepare_picking_default_values_based_on(picking)
        if picking.picking_type_code == "outgoing" and picking.location_id:
            vals["location_dest_id"] = picking.location_id.id
        return vals


class StockReturnPickingLine(models.TransientModel):
    _inherit = "stock.return.picking.line"

    def _prepare_move_default_values(self, new_picking):
        vals = super()._prepare_move_default_values(new_picking)
        picking = self.wizard_id.picking_id
        if picking.picking_type_code == "outgoing" and self.move_id.location_id:
            vals["location_dest_id"] = self.move_id.location_id.id
        return vals
