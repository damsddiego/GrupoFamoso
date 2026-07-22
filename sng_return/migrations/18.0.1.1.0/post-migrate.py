def migrate(cr, version):
    """Vincular las notas de credito existentes (creadas antes del campo
    sng_return_id) con su devolucion, usando el invoice_origin que el modulo
    escribia al generarlas."""
    cr.execute(
        """
        UPDATE account_move am
        SET sng_return_id = sr.id
        FROM sng_return sr
        WHERE am.invoice_origin = sr.name
          AND am.move_type = 'out_refund'
          AND am.company_id = sr.company_id
          AND am.partner_id IS NOT NULL
          AND am.sng_return_id IS NULL
        """
    )
