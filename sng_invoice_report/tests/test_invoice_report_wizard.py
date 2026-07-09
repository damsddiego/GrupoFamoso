from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestInvoiceReportWizard(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesperson = cls.env['res.partner'].create({
            'name': 'Salesperson Report',
            'is_salesperson': True,
        })
        cls.customer = cls.partner_a.copy({
            'name': 'Customer Report',
            'assigned_salesperson_id': cls.salesperson.id,
        })
        cls.company = cls.env.company

        cls.regular_invoice = cls._create_customer_move(
            'out_invoice',
            '2026-04-05',
            100.0,
            salesperson=cls.salesperson,
        )
        cls.origin_invoice = cls._create_customer_move(
            'out_invoice',
            '2026-04-10',
            200.0,
            salesperson=cls.salesperson,
        )
        cls._register_partial_payment(cls.origin_invoice)
        cls.origin_invoice.invalidate_recordset(['payment_state'])

        cls.independent_refund = cls._create_customer_move(
            'out_refund',
            '2026-04-11',
            30.0,
            salesperson=cls.salesperson,
        )
        cls.linked_refund = cls._create_customer_move(
            'out_refund',
            '2026-04-12',
            50.0,
            salesperson=cls.salesperson,
            reversed_entry=cls.origin_invoice,
        )
        cls.cancelled_refund = cls._create_customer_move(
            'out_refund',
            '2026-04-13',
            15.0,
            salesperson=cls.salesperson,
        )
        cls.cancelled_refund.button_cancel()

    @classmethod
    def _create_customer_move(
        cls,
        move_type,
        invoice_date,
        amount,
        salesperson=False,
        reversed_entry=False,
    ):
        move = cls.init_invoice(
            move_type,
            partner=cls.customer,
            invoice_date=fields.Date.from_string(invoice_date),
            amounts=[amount],
            taxes=[],
        )

        values = {}
        if salesperson:
            values['salesperson_id'] = salesperson.id
        if reversed_entry:
            values['reversed_entry_id'] = reversed_entry.id
        if values:
            move.write(values)

        move.action_post()
        return move

    @classmethod
    def _register_partial_payment(cls, invoice):
        cls.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': invoice.amount_total / 2,
            'payment_method_line_id': cls.inbound_payment_method_line.id,
        })._create_payments()

    def _create_wizard(self, **values):
        defaults = {
            'date_from': fields.Date.from_string('2026-04-01'),
            'date_to': fields.Date.from_string('2026-04-30'),
            'company_ids': [Command.set(self.company.ids)],
            'payment_status': 'all',
            'invoice_type': 'out_invoice',
        }
        defaults.update(values)
        return self.env['invoice.report.wizard'].create(defaults)

    def test_out_invoice_includes_credit_notes_without_duplicates(self):
        wizard = self._create_wizard(invoice_type='out_invoice')

        self.assertNotEqual(self.origin_invoice.payment_state, 'not_paid')

        invoices = wizard._get_invoices()

        self.assertCountEqual(invoices.ids, [
            self.regular_invoice.id,
            self.origin_invoice.id,
            self.independent_refund.id,
            self.linked_refund.id,
        ])
        self.assertNotIn(self.cancelled_refund, invoices)
        self.assertEqual(len(invoices), len(set(invoices.ids)))

    def test_out_refund_and_all_modes_share_deduplicated_selection(self):
        refund_wizard = self._create_wizard(invoice_type='out_refund')
        all_wizard = self._create_wizard(invoice_type='all')

        refund_invoices = refund_wizard._get_invoices()
        all_invoices = all_wizard._get_invoices()

        self.assertCountEqual(refund_invoices.ids, [
            self.independent_refund.id,
            self.linked_refund.id,
        ])
        self.assertCountEqual(all_invoices.ids, [
            self.regular_invoice.id,
            self.origin_invoice.id,
            self.independent_refund.id,
            self.linked_refund.id,
        ])

    def test_report_data_orders_linked_credit_note_after_origin(self):
        wizard = self._create_wizard(invoice_type='out_invoice')

        data = wizard._get_report_data()

        self.assertEqual(len(data['data_by_salesperson']), 1)
        invoice_numbers = [
            line['number']
            for line in data['data_by_salesperson'][0]['invoices']
        ]

        self.assertEqual(invoice_numbers, [
            self.regular_invoice.name,
            self.origin_invoice.name,
            f"↳ {self.linked_refund.name}",
            self.independent_refund.name,
        ])

    def test_view_action_uses_same_invoice_universe(self):
        wizard = self._create_wizard(invoice_type='out_invoice')

        invoices = wizard._get_invoices()
        action = wizard.action_view_on_screen()

        self.assertEqual(action['domain'][0][0], 'id')
        self.assertEqual(action['domain'][0][1], 'in')
        self.assertCountEqual(action['domain'][0][2], invoices.ids)
        self.assertEqual(
            action['context']['allowed_company_ids'],
            self.company.ids,
        )
