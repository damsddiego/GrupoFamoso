# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = "res.partner"

    sale_location_id = fields.Many2one('stock.location', string="Ubicación de venta", help="Ubicación a utilizar para proceso de venta",
                                       domain=lambda x: [('usage', '=', 'internal')],)

    team_id = fields.Many2one('crm.team', string="Equipo de ventas")

    def action_open_current_stock_location_report(self):
        self.ensure_one()
        location = self.sale_location_id
        return {
            "type": "ir.actions.act_window",
            "name": "Existencias Actuales por Ubicación",
            "res_model": "current.stock.location.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": self._name,
                "active_id": self.id,
                "active_ids": [self.id],
                "default_partner_ids": [(6, 0, [self.id])],
                "default_location_ids": [(6, 0, location.ids)],
            },
        }
