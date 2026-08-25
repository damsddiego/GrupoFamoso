# -*- coding: utf-8 -*-
"""Backfill de sng_confirmation_date para pagos ya confirmados.

La fecha real de confirmación solo quedó registrada en el chatter
(mail.tracking.value guarda la ETIQUETA traducida del estado, no la clave
técnica). Para pagos sin tracking (p. ej. nacidos ya confirmados desde la
conciliación bancaria) se usa create_date, que en ese flujo es la fecha de
confirmación. Los timestamps están en UTC; el día se toma en hora de Costa
Rica, igual que el sellado en vivo del módulo.
"""


def migrate(cr, version):
    cr.execute("""
        WITH conf AS (
            SELECT m.res_id AS pid,
                   MIN(COALESCE(m.date, m.create_date)) AS first_confirm
            FROM mail_tracking_value tv
            JOIN mail_message m ON m.id = tv.mail_message_id
            JOIN ir_model_fields f ON f.id = tv.field_id
            WHERE m.model = 'account.payment'
              AND f.model = 'account.payment' AND f.name = 'state'
              AND tv.new_value_char IN ('Pagado', 'Paid', 'En proceso', 'In Process')
            GROUP BY m.res_id
        )
        UPDATE account_payment p
        SET sng_confirmation_date = (
                COALESCE(c.first_confirm, p2.create_date)
                AT TIME ZONE 'UTC' AT TIME ZONE 'America/Costa_Rica')::date
        FROM account_payment p2
        LEFT JOIN conf c ON c.pid = p2.id
        WHERE p.id = p2.id
          AND p2.state IN ('in_process', 'paid')
          AND p.sng_confirmation_date IS NULL
    """)

    # Los store de la línea (confirmation_date related, original_period,
    # is_rolled_over) se calcularon durante la carga del módulo con los pagos
    # todavía en NULL; se rehacen aquí con la misma lógica de los computes.
    cr.execute("""
        UPDATE sng_commission_payment_line l
        SET confirmation_date = p.sng_confirmation_date
        FROM account_payment p
        WHERE p.id = l.payment_id
          AND l.confirmation_date IS DISTINCT FROM p.sng_confirmation_date
    """)
    cr.execute("""
        UPDATE sng_commission_payment_line
        SET original_period = date_trunc(
                'month', COALESCE(confirmation_date, payment_date))::date
        WHERE COALESCE(confirmation_date, payment_date) IS NOT NULL
    """)
    cr.execute("""
        UPDATE sng_commission_payment_line
        SET is_rolled_over = (
            period IS NOT NULL
            AND original_period IS NOT NULL
            AND period <> original_period
        )
    """)
