from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOutstandingRefresh(TransactionCase):
    """Facturas marcadas en el pago que ya se pagaron con otro pago.

    Caso real (pago 3820 de prod, 2026-10-15): un pago vuelve a borrador, otra
    factura de su lista queda pagada por otro pago y al confirmar fallaba con
    "No Outstanding Account found", que apunta al diario y no a la factura.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        receivable = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.ids),
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente prueba omax refresh',
            'property_account_receivable_id': receivable.id,
        })
        cls.sale_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'sale'),
            ('default_account_id.account_type', '=', 'income'),
        ], limit=1)
        cls.income_account = cls.sale_journal.default_account_id
        cls.bank_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', 'in', ('bank', 'cash')),
        ], limit=1)

    def _create_invoice(self, amount):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'invoice_date': fields.Date.today(),
            'tipo_documento': 'disabled',
            'invoice_line_ids': [(0, 0, {
                'name': 'Línea',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.income_account.id,
                'tax_ids': [(6, 0, [])],
            })],
        })
        move.action_post()
        return move

    def _create_payment(self, amount, invoices):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': amount,
            'journal_id': self.bank_journal.id,
        })
        payment.action_reload_outstanding_moves()
        payment.outstanding_move_lines.filtered(
            lambda l: l.account_move_id in invoices
        ).select_to_pay = True
        return payment

    def _line(self, payment, invoice):
        return payment.outstanding_move_lines.filtered(
            lambda l: l.account_move_id == invoice
        )

    def test_is_payable_and_warning(self):
        inv1, inv2 = self._create_invoice(100), self._create_invoice(200)
        pay_a = self._create_payment(300, inv1 | inv2)
        self.assertTrue(all(pay_a.outstanding_move_lines.mapped('is_payable')))
        self.assertFalse(pay_a.outstanding_not_payable_names)

        # Otro pago paga inv2 por completo.
        pay_b = self._create_payment(200, inv2)
        pay_b.action_post()
        self.assertIn(inv2.payment_state, ('paid', 'in_payment'))

        line2 = self._line(pay_a, inv2)
        self.assertFalse(line2.is_payable)
        self.assertEqual(line2.payment_state, inv2.payment_state)
        self.assertTrue(self._line(pay_a, inv1).is_payable)
        self.assertIn(inv2.name, pay_a.outstanding_not_payable_names)

    def test_post_with_paid_invoice_selected_raises_clear_error(self):
        inv1, inv2 = self._create_invoice(100), self._create_invoice(200)
        pay_a = self._create_payment(300, inv1 | inv2)
        pay_b = self._create_payment(200, inv2)
        pay_b.action_post()

        with self.assertRaises(UserError) as cm:
            pay_a.action_post()
        self.assertIn(inv2.name, str(cm.exception))
        self.assertIn('Recargar pendientes', str(cm.exception))
        self.assertNotIn('No Outstanding Account', str(cm.exception))
        # Se valida antes de generar el asiento: el pago queda intacto.
        self.assertEqual(pay_a.state, 'draft')
        self.assertFalse(pay_a.move_id)

    def test_reload_keeps_selection_and_drops_paid(self):
        inv1, inv2, inv3 = self._create_invoice(100), self._create_invoice(200), self._create_invoice(50)
        pay_a = self._create_payment(300, inv1 | inv2)  # inv3 queda sin marcar
        pay_a.writeoff_amt = 7.0
        pay_b = self._create_payment(200, inv2)
        pay_b.action_post()

        pay_a.action_reload_outstanding_moves()
        moves = pay_a.outstanding_move_lines.mapped('account_move_id')
        self.assertIn(inv1, moves)
        self.assertIn(inv3, moves)
        self.assertNotIn(inv2, moves)
        self.assertTrue(self._line(pay_a, inv1).select_to_pay)
        self.assertFalse(self._line(pay_a, inv3).select_to_pay)
        self.assertEqual(pay_a.writeoff_amt, 7.0)
        self.assertFalse(pay_a.outstanding_not_payable_names)

        pay_a.action_post()
        self.assertIn(pay_a.state, ('in_process', 'paid'))
        self.assertEqual(inv1.amount_residual, 0)

    def test_draft_refreshes_list(self):
        """Al volver a borrador salen de la lista las facturas pagadas por otros."""
        inv1, inv2 = self._create_invoice(100), self._create_invoice(200)
        pay_a = self._create_payment(100, inv1)
        self.assertIn(inv2, pay_a.outstanding_move_lines.mapped('account_move_id'))
        pay_a.action_post()
        self.assertEqual(inv1.amount_residual, 0)

        pay_b = self._create_payment(200, inv2)
        pay_b.action_post()

        pay_a.action_draft()
        self.assertEqual(pay_a.state, 'draft')
        self.assertFalse(pay_a.move_id)
        moves = pay_a.outstanding_move_lines.mapped('account_move_id')
        # inv1 vuelve a estar abierta y sigue marcada; inv2 ya no aparece.
        self.assertIn(inv1, moves)
        self.assertNotIn(inv2, moves)
        self.assertTrue(self._line(pay_a, inv1).select_to_pay)

        pay_a.action_post()
        self.assertIn(pay_a.state, ('in_process', 'paid'))
        self.assertEqual(inv1.amount_residual, 0)

    def test_draft_without_pay_moves_untouched(self):
        inv1 = self._create_invoice(100)
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100,
            'journal_id': self.bank_journal.id,
        })
        payment.action_post()
        payment.action_draft()
        self.assertEqual(payment.state, 'draft')
        self.assertFalse(payment.outstanding_move_lines)
        self.assertEqual(inv1.amount_residual, 100)
