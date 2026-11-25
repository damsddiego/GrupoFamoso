# -*- coding: utf-8 -*-
"""Crea vacía la columna del control de anulaciones.

sng_estado_control es un campo calculado almacenado nuevo en account.move. Si
el ORM crea la columna, calcula y escribe el campo en todos los asientos de la
base dentro de la actualización, con las filas bloqueadas hasta el commit. Solo
tiene valor en notas de crédito de cliente confirmadas: post-migrate lo calcula
para esas.
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE account_move
        ADD COLUMN IF NOT EXISTS sng_estado_control varchar
    """)
