from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultiPost(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        receivable = cls.env['account.account'].search([
            ('company_ids', 'in', cls.company.ids),
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente prueba omax',
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

    def test_register_payment_multiple_invoices_not_grouped(self):
        """El asistente confirma varios pagos a la vez: no debe fallar."""
        invoices = self._create_invoice(100) | self._create_invoice(200) | self._create_invoice(300)
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoices.ids,
        ).create({
            'journal_id': self.bank_journal.id,
            'group_payment': False,
        })
        payments = wizard._create_payments()
        self.assertEqual(len(payments), 3)
        self.assertTrue(all(p.state != 'draft' for p in payments))
        self.assertTrue(all(inv.payment_state in ('paid', 'in_payment') for inv in invoices))

    def test_post_and_draft_multiple_payments_with_pay_moves(self):
        """action_post / action_draft sobre varios pagos con pay_moves."""
        invoices = self._create_invoice(150) | self._create_invoice(250)
        payments = self.env['account.payment']
        for inv in invoices:
            payment = self.env['account.payment'].create({
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.partner.id,
                'amount': inv.amount_total,
                'journal_id': self.bank_journal.id,
            })
            payment.action_reload_outstanding_moves()
            payment.outstanding_move_lines.filtered(
                lambda l, inv=inv: l.account_move_id == inv
            ).select_to_pay = True
            payments |= payment
        self.assertTrue(all(payments.mapped('pay_moves')))

        payments.action_post()
        self.assertTrue(all(inv.payment_state in ('paid', 'in_payment') for inv in invoices))

        payments.action_draft()
        self.assertTrue(all(p.state == 'draft' for p in payments))
