# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)

TARGET_PRODUCT = '92001006'  # Termo Tumbler


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_custom_move_fields(self):
        return super()._get_custom_move_fields() + ['partner_sale_location_id']

    def _get_stock_move_values(
        self,
        product_id,
        product_qty,
        product_uom,
        location_dest_id,
        name,
        origin,
        company_id,
        values,
    ):
        # Log siempre que se llame, para cualquier producto
        _logger.info(
            '[sale_stock_sng] _get_stock_move_values | product=%s | partner_sale_location_id=%s',
            product_id.display_name,
            values.get('partner_sale_location_id'),
        )

        res = super()._get_stock_move_values(
            product_id,
            product_qty,
            product_uom,
            location_dest_id,
            name,
            origin,
            company_id,
            values,
        )

        partner_loc_id = values.get('partner_sale_location_id')
        if partner_loc_id:
            res['location_id'] = partner_loc_id

        return res


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    def run(self, procurements, raise_user_error=True):
        # Log si algún procurement involucra el producto problemático o Traslado
        for proc in procurements:
            ref = getattr(proc.product_id, 'default_code', '') or ''
            loc_name = proc.location_id.complete_name if proc.location_id else '?'
            if TARGET_PRODUCT in ref or 'Traslado' in loc_name:
                _logger.info(
                    '[sale_stock_sng] procurement.group.run | product=%s | location=%s | values_keys=%s',
                    proc.product_id.display_name,
                    loc_name,
                    list(proc.values.keys()),
                )
        return super().run(procurements, raise_user_error=raise_user_error)
