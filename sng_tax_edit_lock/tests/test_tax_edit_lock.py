from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "sng_tax_edit_lock")
class TestTaxEditLock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.tax_13 = cls.env["account.tax"].create({
            "name": "QA IVA 13%",
            "amount": 13.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.tax_4 = cls.env["account.tax"].create({
            "name": "QA IVA 4%",
            "amount": 4.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "QA Producto Impuesto 13",
            "list_price": 100.0,
            "taxes_id": [Command.set(cls.tax_13.ids)],
        })
        cls.product_4 = cls.env["product.product"].create({
            "name": "QA Producto Impuesto 4",
            "list_price": 100.0,
            "taxes_id": [Command.set(cls.tax_4.ids)],
        })
        cls.product_no_tax = cls.env["product.product"].create({
            "name": "QA Producto Sin Impuesto",
            "list_price": 100.0,
            "taxes_id": [Command.set([])],
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "QA Cliente Bloqueo Impuesto",
        })
        # En bases multi-compania los defaults de cuentas pueden no existir
        # para la compania activa; se asignan explicitamente.
        income_account = cls.env["account.account"].search(
            [
                ("account_type", "=", "income"),
                ("company_ids", "in", cls.company.ids),
            ],
            limit=1,
        )
        receivable_account = cls.env["account.account"].search(
            [
                ("account_type", "=", "asset_receivable"),
                ("company_ids", "in", cls.company.ids),
            ],
            limit=1,
        )
        for product in (cls.product, cls.product_4, cls.product_no_tax):
            product.with_company(
                cls.company
            ).property_account_income_id = income_account
        cls.partner.with_company(
            cls.company
        ).property_account_receivable_id = receivable_account
        cls.normal_user = new_test_user(
            cls.env,
            login="qa_tax_edit_normal",
            groups=(
                "sales_team.group_sale_salesman,"
                "account.group_account_invoice"
            ),
            company_id=cls.company.id,
        )
        cls.admin_user = new_test_user(
            cls.env,
            login="qa_tax_edit_admin",
            groups=(
                "base.group_system,"
                "sales_team.group_sale_manager,"
                "account.group_account_manager"
            ),
            company_id=cls.company.id,
        )
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "user_id": cls.normal_user.id,
            "order_line": [Command.create({
                "product_id": cls.product.id,
                "product_uom_qty": 1.0,
            })],
        })
        cls.invoice = cls.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": cls.partner.id,
            "invoice_line_ids": [Command.create({
                "product_id": cls.product.id,
                "quantity": 1.0,
            })],
        })

    def test_normal_user_cannot_change_sale_line_tax(self):
        line = self.order.order_line.with_user(self.normal_user)
        self.assertFalse(line.sng_tax_edit_allowed)
        with self.assertRaises(AccessError), self.cr.savepoint():
            line.write({"tax_id": [Command.set(self.tax_4.ids)]})

    def test_normal_user_can_remove_sale_line_tax(self):
        line = self.order.order_line.with_user(self.normal_user)
        line.write({"tax_id": [Command.clear()]})
        self.assertFalse(line.tax_id)

    def test_normal_user_can_create_sale_line_without_tax(self):
        line = self.env["sale.order.line"].with_user(self.normal_user).create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "tax_id": [Command.set([])],
        })
        self.assertFalse(line.tax_id)

    def test_normal_user_cannot_change_invoice_line_tax(self):
        line = self.invoice.invoice_line_ids.with_user(self.normal_user)
        self.assertFalse(line.sng_tax_edit_allowed)
        with self.assertRaises(AccessError), self.cr.savepoint():
            line.write({"tax_ids": [Command.set(self.tax_4.ids)]})

    def test_unchanged_tax_value_is_allowed(self):
        sale_line = self.order.order_line.with_user(self.normal_user)
        invoice_line = self.invoice.invoice_line_ids.with_user(self.normal_user)
        sale_line.write({"tax_id": [Command.set(sale_line.tax_id.ids)]})
        invoice_line.write({
            "tax_ids": [Command.set(invoice_line.tax_ids.ids)],
        })

    def test_system_admin_can_change_taxes(self):
        sale_line = self.order.order_line.with_user(self.admin_user)
        invoice_line = self.invoice.invoice_line_ids.with_user(self.admin_user)

        self.assertTrue(sale_line.sng_tax_edit_allowed)
        self.assertTrue(invoice_line.sng_tax_edit_allowed)
        sale_line.write({"tax_id": [Command.set(self.tax_4.ids)]})
        invoice_line.write({"tax_ids": [Command.set(self.tax_4.ids)]})

        self.assertEqual(sale_line.tax_id, self.tax_4)
        self.assertEqual(invoice_line.tax_ids, self.tax_4)

    def test_normal_user_cannot_create_sale_line_with_custom_tax(self):
        order = self.order.with_user(self.normal_user)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["sale.order.line"].with_user(self.normal_user).create({
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "tax_id": [Command.set(self.tax_4.ids)],
            })

    def test_normal_user_can_create_sale_line_with_default_tax(self):
        line = self.env["sale.order.line"].with_user(self.normal_user).create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "tax_id": [Command.set(self.tax_13.ids)],
        })
        self.assertEqual(line.tax_id, self.tax_13)

    def test_admin_can_create_sale_line_with_custom_tax(self):
        line = self.env["sale.order.line"].with_user(self.admin_user).create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "tax_id": [Command.set(self.tax_4.ids)],
        })
        self.assertEqual(line.tax_id, self.tax_4)

    def test_can_confirm_order_without_tax(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [Command.create({
                "product_id": self.product_no_tax.id,
                "product_uom_qty": 1.0,
            })],
        })
        self.assertFalse(order.order_line.tax_id)
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_cannot_post_invoice_without_tax(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_line_ids": [Command.create({
                "product_id": self.product_no_tax.id,
                "quantity": 1.0,
            })],
        })
        self.assertNotEqual(invoice.tipo_documento, "disabled")
        # Aplica a todos los usuarios, incluidos administradores.
        with self.assertRaises(UserError), self.cr.savepoint():
            invoice.with_user(self.admin_user).action_post()

    def test_can_post_disabled_invoice_without_tax(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "tipo_documento": "disabled",
            "invoice_line_ids": [Command.create({
                "product_id": self.product_no_tax.id,
                "quantity": 1.0,
            })],
        })
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_otros_cargos_lines_do_not_require_tax(self):
        categ = self.env["product.category"].create({"name": "Otros Cargos"})
        product_oc = self.env["product.product"].create({
            "name": "QA Otro Cargo",
            "list_price": 10.0,
            "categ_id": categ.id,
            "taxes_id": [Command.set([])],
        })
        product_oc.with_company(self.company).property_account_income_id = (
            self.product.with_company(self.company).property_account_income_id
        )
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                }),
                Command.create({
                    "product_id": product_oc.id,
                    "quantity": 1.0,
                }),
            ],
        })
        self.assertTrue(invoice._sng_tax_required_for_post())
        self.assertFalse(invoice._sng_lines_missing_tax())

    def test_can_confirm_order_with_taxes(self):
        self.order.action_confirm()
        self.assertEqual(self.order.state, "sale")

    def test_normal_user_can_remove_tax_when_edocs_disabled(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "tipo_documento": "disabled",
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id,
                "quantity": 1.0,
            })],
        })
        line = invoice.invoice_line_ids.with_user(self.normal_user)
        self.assertTrue(line.sng_tax_edit_allowed)
        line.write({"tax_ids": [Command.clear()]})
        self.assertFalse(line.tax_ids)

    def test_switching_tipo_documento_toggles_lock(self):
        line = self.invoice.invoice_line_ids.with_user(self.normal_user)
        self.assertFalse(line.sng_tax_edit_allowed)

        self.invoice.tipo_documento = "disabled"
        line.invalidate_recordset(["sng_tax_edit_allowed"])
        self.assertTrue(line.sng_tax_edit_allowed)

        self.invoice.tipo_documento = "FE"
        line.invalidate_recordset(["sng_tax_edit_allowed"])
        self.assertFalse(line.sng_tax_edit_allowed)
        with self.assertRaises(AccessError), self.cr.savepoint():
            line.write({"tax_ids": [Command.clear()]})

    def test_automatic_product_tax_recompute_remains_available(self):
        sale_line = self.order.order_line.with_user(self.normal_user)
        invoice_line = self.invoice.invoice_line_ids.with_user(self.normal_user)

        sale_line.write({"product_id": self.product_4.id})
        invoice_line.write({"product_id": self.product_4.id})

        self.assertEqual(sale_line.tax_id, self.tax_4)
        self.assertEqual(invoice_line.tax_ids, self.tax_4)
