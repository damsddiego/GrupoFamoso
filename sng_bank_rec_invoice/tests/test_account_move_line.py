from odoo.tests.common import TransactionCase


class TestAccountMoveLineInvoiceSequence(TransactionCase):
    def test_invoice_sequence_is_shown_for_invoice(self):
        invoice = self.env["account.move"].new(
            {
                "move_type": "out_invoice",
                "name": "INV/TEST/0001",
            }
        )
        line = self.env["account.move.line"].new({"move_id": invoice})

        line._compute_sng_invoice_sequence()

        self.assertEqual(line.sng_invoice_sequence, "INV/TEST/0001")

    def test_invoice_sequence_is_empty_for_journal_entry(self):
        entry = self.env["account.move"].new(
            {
                "move_type": "entry",
                "name": "MISC/TEST/0001",
            }
        )
        line = self.env["account.move.line"].new({"move_id": entry})

        line._compute_sng_invoice_sequence()

        self.assertFalse(line.sng_invoice_sequence)
