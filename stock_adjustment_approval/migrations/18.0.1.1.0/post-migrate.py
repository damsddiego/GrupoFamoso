# -*- coding: utf-8 -*-
"""Llena Ajuste (+/-) en los borradores y Stock al Aprobar / Diferencia Aplicada
en las líneas ya aprobadas.

Borradores: el ajuste es contado - stock actual, que es la "Diferencia" que el
usuario veía en pantalla. Si la cantidad contada quedó en 0 (línea sin llenar)
el ajuste queda en 0 para no vaciar la ubicación por accidente al enviar.

Hasta la 18.0.1.0.2 la aprobación fijaba la cantidad contada tal cual, así que lo
aplicado es la suma con signo de los movimientos vinculados y el stock al aprobar
era contado - aplicado. Así las solicitudes viejas muestran cuándo lo aplicado no
coincide con lo pedido.
"""


from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    drafts = env['stock.adjustment.request.line'].search([
        ('state', '=', 'draft'), ('adjustment_quantity', '=', False),
    ])
    for line in drafts.with_context(active_test=False):
        if line.counted_quantity:
            adjustment = line.counted_quantity - line.current_quantity
        else:
            adjustment = 0.0
        line.with_company(line.company_id).adjustment_quantity = adjustment

    cr.execute("""
        UPDATE stock_adjustment_request_line l
           SET applied_difference = sub.applied,
               quantity_at_approval = l.counted_quantity - sub.applied
          FROM (
                SELECT l2.id,
                       COALESCE(SUM(CASE WHEN m.location_dest_id = l2.location_id
                                         THEN m.quantity ELSE -m.quantity END), 0) AS applied
                  FROM stock_adjustment_request_line l2
             LEFT JOIN stock_adjustment_request_line_stock_move_rel r ON r.line_id = l2.id
             LEFT JOIN stock_move m ON m.id = r.move_id AND m.state = 'done'
                 WHERE l2.applied
              GROUP BY l2.id
               ) sub
         WHERE sub.id = l.id
           AND l.applied_difference IS NULL
    """)
