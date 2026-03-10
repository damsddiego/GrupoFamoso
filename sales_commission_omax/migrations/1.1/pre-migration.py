# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Pre-migration script to prepare database for migration"""
    _logger.info("Starting pre-migration of sales_commission_omax to version 1.1")

    # Eliminar la tabla partner_commission_rel si existe (será recreada con la estructura correcta)
    cr.execute("""
        DROP TABLE IF EXISTS partner_commission_rel CASCADE
    """)
    _logger.info("Dropped old partner_commission_rel table if it existed")

    _logger.info("Pre-migration to version 1.1 completed successfully")
