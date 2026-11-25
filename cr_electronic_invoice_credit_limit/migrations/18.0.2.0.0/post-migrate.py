# -*- coding: utf-8 -*-
"""Calcula el control de anulaciones y autoriza a quienes crean NC.

pre-migrate dejó la columna del control vacía para no recalcular todos los
asientos: aquí se calcula solo en las notas de crédito ya confirmadas.
"""
from odoo import SUPERUSER_ID, api

# Usuarios que diego autorizó el 2026-11-25 a crear notas de crédito de
# cliente; el administrador entra por el XML del grupo.
USUARIOS_AUTORIZADOS_NC = (
    'eobregon@grupofsa.net',
    'sherrera@grupofsa.net',
    'gerencia@grupofsa.net',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    credit_notes = env['account.move'].with_context(active_test=False).search([
        ('move_type', '=', 'out_refund'),
        ('state', '=', 'posted'),
    ])
    env.add_to_compute(credit_notes._fields['sng_estado_control'], credit_notes)
    credit_notes.flush_recordset(['sng_estado_control'])

    group = env.ref('cr_electronic_invoice_credit_limit.group_sng_crear_nota_credito')
    users = env['res.users'].with_context(active_test=False).search([
        ('login', 'in', USUARIOS_AUTORIZADOS_NC),
    ])
    group.write({'users': [(4, user.id) for user in users]})
