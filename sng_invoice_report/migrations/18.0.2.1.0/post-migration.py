from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Recompute effective_salesperson_id with the new is_salesperson-aware logic.

    Invoices whose salesperson fallback resolved to a non-salesperson partner
    (invoice user / current user) must now group under 'Sin asignar'.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env['account.move'].search([
        ('move_type', 'in', ['out_invoice', 'out_refund']),
    ])
    env.add_to_compute(moves._fields['effective_salesperson_id'], moves)
    moves.flush_model(['effective_salesperson_id'])
