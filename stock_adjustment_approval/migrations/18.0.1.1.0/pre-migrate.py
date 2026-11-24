# -*- coding: utf-8 -*-
"""Crea Ajuste (+/-) a partir de la cantidad contada de las líneas ya enviadas.

Hasta la 18.0.1.0.2 el usuario escribía la cantidad contada; ahora escribe el
ajuste con signo. En las líneas enviadas/aprobadas/rechazadas el ajuste pedido
es contado - teórico al enviar. Los borradores se tratan en post-migrate, porque
necesitan el stock actual.
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE stock_adjustment_request_line
        ADD COLUMN IF NOT EXISTS adjustment_quantity numeric
    """)
    cr.execute("""
        UPDATE stock_adjustment_request_line l
           SET adjustment_quantity = l.counted_quantity - COALESCE(l.theoretical_quantity, 0)
          FROM stock_adjustment_request r
         WHERE r.id = l.request_id
           AND r.state != 'draft'
           AND l.adjustment_quantity IS NULL
    """)
