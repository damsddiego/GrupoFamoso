from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestSngReturnStock(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.write({
            "groups_id": [(4, cls.env.ref("sng_return.group_sng_return_supervisor").id)]
        })
        cls.company.payment_method_default_id = cls.env.ref(
            "cr_electronic_invoice.PaymentMethods_1"
        )
        cls.income_account = cls.env["account.account"].create({
            "name": "Ingresos de prueba",
            "code": "TSTINC",
            "account_type": "income",
            "company_ids": [(6, 0, cls.company.ids)],
        })
        cls.receivable_account = cls.env["account.account"].create({
            "name": "Cuentas por cobrar de prueba",
            "code": "TSTREC",
            "account_type": "asset_receivable",
            "reconcile": True,
            "company_ids": [(6, 0, cls.company.ids)],
        })
        cls.env["account.journal"].create({
            "name": "Ventas de prueba",
            "code": "TSAL",
            "type": "sale",
            "company_id": cls.company.id,
            "default_account_id": cls.income_account.id,
        })
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)],
            limit=1,
        )
        cls.partner = cls.env["res.partner"].create({
            "name": "Cliente devolución",
            "customer_rank": 1,
            "property_account_receivable_id": cls.receivable_account.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Producto retornable",
            "is_storable": True,
            "list_price": 100.0,
            "property_account_income_id": cls.income_account.id,
        })
        cls.reason = cls.env["sng.return.reason"].create({
            "name": "Producto no requerido",
        })
        cls.sale_order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "warehouse_id": cls.warehouse.id,
            "order_line": [(0, 0, {
                "product_id": cls.product.id,
                "product_uom_qty": 2.0,
                "price_unit": 100.0,
            })],
        })
        cls.sale_order.action_confirm()
        cls.invoice = cls.sale_order._create_invoices()

    def _create_return(self):
        return self.env["sng.return"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "reason_id": self.reason.id,
            "line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1.0,
                "invoice_id": self.invoice.id,
            })],
        })

    def test_confirmation_creates_pending_receipt(self):
        customer_return = self._create_return()

        action = customer_return.action_confirm()

        self.assertEqual(customer_return.state, "draft")
        self.assertEqual(action["res_model"], "sng.return.confirm.wizard")

        wizard = self.env[action["res_model"]].browse(action["res_id"])
        wizard.warehouse_id = self.warehouse
        wizard.action_confirm()

        self.assertEqual(customer_return.state, "confirmed")
        self.assertEqual(customer_return.warehouse_id, self.warehouse)
        self.assertTrue(customer_return.picking_id)
        self.assertEqual(customer_return.picking_id.sng_return_id, customer_return)
        self.assertEqual(
            customer_return.picking_id.location_id,
            self.partner.property_stock_customer,
        )
        self.assertEqual(
            customer_return.picking_id.location_dest_id,
            customer_return.location_dest_id,
        )
        self.assertEqual(customer_return.picking_id.move_ids.product_id, self.product)
        self.assertEqual(customer_return.picking_id.move_ids.product_uom_qty, 1.0)
        self.assertEqual(customer_return.receipt_state, "pending")
        self.assertFalse(customer_return.receipt_complete)

    def test_credit_note_requires_completed_receipt(self):
        customer_return = self._create_return()
        customer_return._confirm_with_warehouse(self.warehouse)

        with self.assertRaisesRegex(UserError, "recibir completamente"):
            customer_return.action_generate_credit_note()

        picking = customer_return.picking_id
        picking.move_ids.quantity = picking.move_ids.product_uom_qty
        picking.button_validate()
        customer_return.invalidate_recordset(["receipt_complete", "receipt_state"])

        self.assertEqual(customer_return.receipt_state, "done")
        self.assertTrue(customer_return.receipt_complete)

        action = customer_return.action_generate_credit_note()
        credit_note = self.env["account.move"].browse(action["res_id"])

        self.assertEqual(credit_note.sng_return_id, customer_return)
        self.assertEqual(credit_note.sng_return_warehouse_id, self.warehouse)
        self.assertEqual(
            credit_note.sng_return_location_id,
            customer_return.location_dest_id,
        )
        self.assertEqual(credit_note.sng_return_picking_id, picking)
        if "return_location_id" in credit_note._fields:
            self.assertEqual(
                credit_note.return_location_id,
                customer_return.location_dest_id,
            )
        if "stock_return_picking_id" in credit_note._fields:
            self.assertEqual(credit_note.stock_return_picking_id, picking)

        with self.assertRaisesRegex(UserError, "nota de crédito activa"):
            customer_return.line_ids.invoice_id = False

    def test_invoice_can_be_selected_after_confirmation(self):
        customer_return = self._create_return()
        customer_return.line_ids.invoice_id = False
        customer_return._confirm_with_warehouse(self.warehouse)

        customer_return.line_ids.invoice_id = self.invoice

        self.assertEqual(customer_return.line_ids.invoice_id, self.invoice)
        with self.assertRaisesRegex(UserError, "solo puede modificar la factura"):
            customer_return.line_ids.quantity = 2.0

    def test_available_quantity_ignores_salesperson_record_rule(self):
        self.invoice.action_post()
        customer_return = self._create_return()
        limited_user = self.env["res.users"].create({
            "name": "Supervisor de devoluciones limitado",
            "login": "limited-return-supervisor",
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
            "groups_id": [(6, 0, [
                self.env.ref("sales_team.group_sale_salesman").id,
                self.env.ref("sng_return.group_sng_return_supervisor").id,
            ])],
        })

        self.assertFalse(
            self.env["sale.order"].with_user(limited_user).search_count([
                ("id", "=", self.sale_order.id),
            ]),
        )

        return_line = customer_return.line_ids.with_user(limited_user)
        return_line.invalidate_recordset([
            "invoiced_sale_qty",
            "previous_return_qty",
            "credit_note_qty",
            "available_return_qty",
            "invoiced_sale_order_count",
        ])

        self.assertEqual(return_line.invoiced_sale_qty, 2.0)
        self.assertEqual(return_line.available_return_qty, 2.0)
