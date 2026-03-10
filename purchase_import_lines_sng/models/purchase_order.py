# -*- coding: utf-8 -*-

from odoo import models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_open_import_wizard(self):
        """Open wizard to import purchase lines from Excel"""
        self.ensure_one()
        return {
            'name': _('Import Purchase Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.purchase.lines.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }
