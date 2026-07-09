# -*- coding: utf-8 -*-
import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    partner_sale_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación consignación cliente',
        copy=False,
    )

    def _action_confirm(self, merge=True, merge_into=False):
        _logger.info(
            '[sale_stock_sng] _action_confirm llamado para %d movimiento(s): %s',
            len(self), self.ids
        )
        for move in self:
            _logger.info(
                '[sale_stock_sng]   move id=%d | product=%s | location_id=%s | '
                'procure_method=%s | partner_sale_location_id=%s',
                move.id,
                move.product_id.display_name,
                move.location_id.complete_name,
                move.procure_method,
                move.partner_sale_location_id.complete_name if move.partner_sale_location_id else 'None',
            )

        consign_moves = self.filtered('partner_sale_location_id')
        if consign_moves:
            _logger.info(
                '[sale_stock_sng] Forzando make_to_stock en %d movimiento(s) de consignación: %s',
                len(consign_moves), consign_moves.ids
            )
            consign_moves.write({'procure_method': 'make_to_stock'})
        else:
            _logger.info('[sale_stock_sng] Ningún movimiento con partner_sale_location_id en este lote.')

        return super()._action_confirm(merge=merge, merge_into=merge_into)
