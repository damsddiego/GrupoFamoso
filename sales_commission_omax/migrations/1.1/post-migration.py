# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migration script to migrate from res.users to res.partner for salespersons"""
    env = api.Environment(cr, SUPERUSER_ID, {})

    _logger.info("Starting migration of sales_commission_omax to version 1.1")

    # Actualizar registros existentes de comisiones para asegurar que los nuevos campos estén disponibles
    sales_commissions = env['sales.commission'].search([])

    for commission in sales_commissions:
        # Establecer valores predeterminados para los nuevos campos
        commission.write({
            'commission_by_days': False,
            'days_0_30_commission': 0.0,
            'days_31_60_commission': 0.0,
            'days_61_90_commission': 0.0,
            'days_90_plus_commission': 0.0,
        })

    # Migrar salesperson_ids de res.users a res.partner
    # Primero, obtenemos todos los usuarios que están asignados a comisiones
    cr.execute("""
        SELECT DISTINCT user_id
        FROM user_commission_rel
        WHERE user_id IS NOT NULL
    """)
    user_ids = [row[0] for row in cr.fetchall()]

    if user_ids:
        _logger.info(f"Found {len(user_ids)} users to migrate")

        # Marcar los partners correspondientes como vendedores
        for user_id in user_ids:
            user = env['res.users'].browse(user_id)
            if user.exists() and user.partner_id:
                user.partner_id.write({'is_salesperson': True})
                _logger.info(f"Marked partner {user.partner_id.name} as salesperson")

        # Migrar las relaciones de la tabla antigua a la nueva
        # Solo migramos registros donde tanto la comisión como el usuario/partner existen
        cr.execute("""
            INSERT INTO partner_commission_rel (commission_id, partner_id)
            SELECT ucr.commission_id, u.partner_id
            FROM user_commission_rel ucr
            JOIN res_users u ON u.id = ucr.user_id
            JOIN sales_commission sc ON sc.id = ucr.commission_id
            WHERE u.partner_id IS NOT NULL
            ON CONFLICT DO NOTHING
        """)
        _logger.info("Migrated commission relationships to new table")

    # Migrar sales_person_id en sales.commission.analysis
    cr.execute("""
        UPDATE sales_commission_analysis sca
        SET sales_person_id = u.partner_id
        FROM res_users u
        WHERE sca.sales_person_id = u.id
        AND u.partner_id IS NOT NULL
    """)
    _logger.info("Migrated sales_person_id in sales.commission.analysis")

    # Migrar salesperson_id en sale.order (desde user_id)
    cr.execute("""
        UPDATE sale_order so
        SET salesperson_id = u.partner_id
        FROM res_users u
        WHERE so.user_id = u.id
        AND u.partner_id IS NOT NULL
        AND so.salesperson_id IS NULL
    """)
    _logger.info("Migrated salesperson_id in sale.order")

    # Migrar salesperson_id en account.move (desde invoice_user_id)
    cr.execute("""
        UPDATE account_move am
        SET salesperson_id = u.partner_id
        FROM res_users u
        WHERE am.invoice_user_id = u.id
        AND u.partner_id IS NOT NULL
        AND am.salesperson_id IS NULL
    """)
    _logger.info("Migrated salesperson_id in account.move")

    _logger.info("Migration to version 1.1 completed successfully")