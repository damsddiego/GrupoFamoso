# -*- coding: utf-8 -*-

from odoo import models


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    def unlink(self):
        # Al romper la aplicación pago↔factura, la comisión de ese par deja de
        # tener sustento: se recolectan los pares antes de borrar los partials
        # y luego se delega en el pago (elimina líneas de meses en borrador,
        # crea reversos para meses cerrados). Idempotente: si el par ya fue
        # tratado (p. ej. por la cancelación del pago que disparó esta
        # desconciliación), no hace nada.
        pairs = []
        for partial in self:
            for pay_line, other_line in (
                (partial.credit_move_id, partial.debit_move_id),
                (partial.debit_move_id, partial.credit_move_id),
            ):
                payment = pay_line.move_id.origin_payment_id
                invoice = other_line.move_id
                if (
                    payment
                    and payment.payment_type == 'inbound'
                    and invoice.move_type in ('out_invoice', 'out_refund')
                ):
                    pairs.append((payment, invoice))
        res = super().unlink()
        for payment, invoice in pairs:
            payment._sng_handle_payment_invalidation('unreconciled', invoices=invoice)
        return res
