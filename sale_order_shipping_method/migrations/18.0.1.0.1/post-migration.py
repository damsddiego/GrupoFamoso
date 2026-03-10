def migrate(cr, version):
    """
    Migración para actualizar facturas existentes con el shipping_method
    de sus pedidos de venta asociados.
    """
    # Actualizar facturas que tienen pedidos de venta con shipping_method
    cr.execute("""
        UPDATE account_move am
        SET shipping_method = so.shipping_method
        FROM sale_order so
        WHERE am.invoice_origin = so.name
          AND so.shipping_method IS NOT NULL
          AND so.shipping_method != ''
          AND am.move_type = 'out_invoice'
          AND (am.shipping_method IS NULL OR am.shipping_method = '')
    """)

    # Registrar cuántas facturas fueron actualizadas
    cr.execute("SELECT COUNT(*) FROM account_move WHERE shipping_method IS NOT NULL")
    count = cr.fetchone()[0]

    # Log en el servidor
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info(f"Migración completada: {count} facturas ahora tienen shipping_method")
