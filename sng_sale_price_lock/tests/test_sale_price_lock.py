from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'sng_sale_price_lock')
class TestSalePriceLock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Odoo solo muestra el descuento de una regla porcentual cuando la
        # funcion de descuentos esta habilitada globalmente.
        cls.env.user.write({
            'groups_id': [
                Command.link(cls.env.ref('sale.group_discount_per_so_line').id),
            ],
        })
        cls.company.write({
            'sng_lock_price_unit': True,
            'sng_lock_discount': True,
            'sng_price_lock_mode': 'exact',
            'sng_discount_lock_mode': 'exact',
            'sng_price_lock_tolerance': 0.0,
        })

        cls.income_account = cls._create_account(
            'QA Income', 'QAINC', 'income'
        )
        cls.expense_account = cls._create_account(
            'QA Expense', 'QAEXP', 'expense'
        )
        cls.receivable_account = cls._create_account(
            'QA Receivable', 'QAREC', 'asset_receivable', reconcile=True
        )
        cls.payable_account = cls._create_account(
            'QA Payable', 'QAPAY', 'liability_payable', reconcile=True
        )
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'QA Sales Journal',
            'code': 'QASJ',
            'type': 'sale',
            'company_id': cls.company.id,
        })
        cls.purchase_journal = cls.env['account.journal'].create({
            'name': 'QA Purchase Journal',
            'code': 'QAPJ',
            'type': 'purchase',
            'company_id': cls.company.id,
        })
        cls.pricelist = cls.env['product.pricelist'].create({
            'name': 'QA Pricelist 10 percent',
            'currency_id': cls.company.currency_id.id,
            'company_id': cls.company.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'QA Price Lock Customer',
        })
        cls.partner.with_company(cls.company).write({
            'property_product_pricelist': cls.pricelist.id,
            'property_account_receivable_id': cls.receivable_account.id,
            'property_account_payable_id': cls.payable_account.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'QA Price Lock Product',
            'list_price': 100.0,
            'sale_ok': True,
            'purchase_ok': True,
            'type': 'service',
            'invoice_policy': 'order',
            'property_account_income_id': cls.income_account.id,
            'property_account_expense_id': cls.expense_account.id,
            'taxes_id': [Command.clear()],
            'supplier_taxes_id': [Command.clear()],
        })
        cls.rule = cls.env['product.pricelist.item'].create({
            'pricelist_id': cls.pricelist.id,
            'compute_price': 'percentage',
            'percent_price': 10.0,
            'applied_on': '1_product',
            'product_tmpl_id': cls.product.product_tmpl_id.id,
        })
        cls.privileged_user = new_test_user(
            cls.env,
            login='qa_price_lock_privileged',
            groups=(
                'account.group_account_invoice,'
                'sales_team.group_sale_salesman,'
                'sng_sale_price_lock.group_sng_force_price'
            ),
            company_id=cls.company.id,
        )

    @classmethod
    def _create_account(cls, name, code, account_type, reconcile=False):
        return cls.env['account.account'].create({
            'name': name,
            'code': code,
            'account_type': account_type,
            'reconcile': reconcile,
            'company_ids': [Command.link(cls.company.id)],
        })

    def setUp(self):
        super().setUp()
        self.company.write({
            'sng_lock_price_unit': True,
            'sng_lock_discount': True,
            'sng_price_lock_mode': 'exact',
            'sng_discount_lock_mode': 'exact',
            'sng_price_lock_tolerance': 0.0,
            'sale_discount_product_id': False,
        })

    def _create_customer_invoice(self, move_type='out_invoice', line_vals=None):
        values = {
            'product_id': self.product.id,
            'quantity': 2.0,
            **(line_vals or {}),
        }
        return self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'invoice_line_ids': [Command.create(values)],
        })

    def test_manual_invoice_uses_customer_pricelist(self):
        invoice = self._create_customer_invoice()
        line = invoice.invoice_line_ids

        self.assertEqual(invoice.sng_pricelist_id, self.pricelist)
        self.assertEqual(line.price_unit, 100.0)
        self.assertEqual(line.discount, 10.0)
        self.assertTrue(line.sng_price_locked)
        self.assertTrue(line.sng_discount_locked)

    def test_manual_invoice_does_not_keep_invalid_values(self):
        # En la creacion anidada, account.move puede recalcular price_unit
        # antes de la barrera final. Lo importante es que el 90 capturado no
        # sobreviva en la factura.
        normalized_invoice = self._create_customer_invoice(line_vals={
            'price_unit': 90.0,
            'discount': 10.0,
        })
        self.assertEqual(normalized_invoice.invoice_line_ids.price_unit, 100.0)

        invoice = self._create_customer_invoice()
        with self.assertRaises(UserError), self.cr.savepoint():
            invoice.invoice_line_ids.write({'discount': 20.0})

    def test_posting_is_a_final_backstop(self):
        invoice = self._create_customer_invoice()
        line = invoice.invoice_line_ids
        line.with_context(sng_skip_price_lock=True).write({'price_unit': 80.0})

        with self.assertRaises(UserError), self.cr.savepoint():
            invoice.action_post()

        line.with_context(sng_skip_price_lock=True).write({'price_unit': 100.0})
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

    def test_invoice_created_from_sale_keeps_commercial_terms(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'pricelist_id': self.pricelist.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
                'discount': 10.0,
            })],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        line = invoice.invoice_line_ids.filtered(
            lambda invoice_line: invoice_line.product_id == self.product
        )

        self.assertEqual(line.sale_line_ids, order.order_line)
        self.assertEqual(line.price_unit, order.order_line.price_unit)
        self.assertEqual(line.discount, order.order_line.discount)
        with self.assertRaises(UserError), self.cr.savepoint():
            line.write({'price_unit': 50.0})

    def test_price_mode_allows_only_higher_prices(self):
        invoice = self._create_customer_invoice()
        line = invoice.invoice_line_ids
        self.company.sng_price_lock_mode = 'no_lower'

        line.write({'price_unit': 110.0})
        self.assertEqual(line.price_unit, 110.0)
        with self.assertRaises(UserError), self.cr.savepoint():
            line.write({'price_unit': 99.0})

    def test_discount_mode_allows_only_lower_discounts(self):
        invoice = self._create_customer_invoice()
        line = invoice.invoice_line_ids
        self.company.sng_discount_lock_mode = 'no_higher'

        line.write({'discount': 5.0})
        self.assertEqual(line.discount, 5.0)
        with self.assertRaises(UserError), self.cr.savepoint():
            line.write({'discount': 11.0})

    def test_percentage_tolerance(self):
        invoice = self._create_customer_invoice()
        line = invoice.invoice_line_ids
        self.company.sng_price_lock_tolerance = 2.0

        line.write({'price_unit': 99.0})
        line.write({'discount': 10.1})
        self.assertEqual(line.price_unit, 99.0)
        self.assertEqual(line.discount, 10.1)
        with self.assertRaises(UserError), self.cr.savepoint():
            line.write({'price_unit': 97.0})

    def test_privileged_group_and_automation_context(self):
        invoice = self._create_customer_invoice()
        line = invoice.invoice_line_ids

        privileged_line = line.with_user(self.privileged_user)
        privileged_line.write({'price_unit': 70.0, 'discount': 30.0})
        self.assertFalse(privileged_line.sng_price_locked)
        self.assertFalse(privileged_line.sng_discount_locked)

        line.with_context(sng_skip_price_lock=True).write({
            'price_unit': 60.0,
            'discount': 40.0,
        })
        self.assertEqual(line.price_unit, 60.0)
        self.assertEqual(line.discount, 40.0)

    def test_credit_note_is_protected(self):
        credit_note = self._create_customer_invoice(move_type='out_refund')
        self.assertEqual(credit_note.invoice_line_ids.price_unit, 100.0)
        with self.assertRaises(UserError), self.cr.savepoint():
            credit_note.invoice_line_ids.write({'price_unit': 90.0})

    def test_vendor_bill_is_outside_scope(self):
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.purchase_journal.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product.id,
                'quantity': 1.0,
                'price_unit': 37.0,
                'discount': 18.0,
            })],
        })
        line = bill.invoice_line_ids

        self.assertFalse(line.sng_price_locked)
        self.assertFalse(line.sng_discount_locked)
        line.write({'price_unit': 12.0, 'discount': 25.0})
        self.assertEqual(line.price_unit, 12.0)
        self.assertEqual(line.discount, 25.0)

    def test_global_discount_product_is_outside_scope(self):
        discount_product = self.env['product.product'].create({
            'name': 'QA Global Discount Product',
            'list_price': 0.0,
            'sale_ok': True,
            'type': 'service',
            'property_account_income_id': self.income_account.id,
            'taxes_id': [Command.clear()],
        })
        self.company.sale_discount_product_id = discount_product
        invoice = self._create_customer_invoice(line_vals={
            'product_id': discount_product.id,
            'price_unit': -35.0,
            'discount': 0.0,
        })

        self.assertFalse(invoice.invoice_line_ids.sng_price_locked)
        invoice.invoice_line_ids.write({'price_unit': -50.0})
        self.assertEqual(invoice.invoice_line_ids.price_unit, -50.0)
