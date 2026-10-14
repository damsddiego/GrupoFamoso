# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEnforceServer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Enforce Demo",
            "login": "sng_enforce_demo@example.test",
            "groups_id": [(6, 0, [
                cls.env.ref("sales_team.group_sale_salesman").id,
            ])],
        })
        cls.partner = cls.env["res.partner"].create({"name": "Cliente enforce"})
        cls.product = cls.env["product.product"].create({
            "name": "Producto enforce", "type": "service", "list_price": 10,
        })
        cls.model_so = cls.env["ir.model"]._get("sale.order")
        cls.profile = cls.env["eh.access.profile"].create({
            "name": "Test enforce",
            "user_ids": [(6, 0, [cls.user.id])],
            "node_line_ids": [(0, 0, {
                "model_id": cls.model_so.id,
                "kind": "button",
                "target_name": "action_confirm",
                "enforce_server": True,
            })],
        })

    def _new_order(self):
        return self.env["sale.order"].with_user(self.user).create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})],
        })

    def test_blocked_for_profile_user(self):
        order = self._new_order()
        with self.assertRaises(AccessError):
            order.action_confirm()
        self.assertEqual(order.state, "draft")

    def test_blocked_at_inner_gate(self):
        # Un override de action_confirm que llegue a _action_confirm sin
        # pasar por nuestro action_confirm también queda bloqueado.
        order = self._new_order()
        with self.assertRaises(AccessError):
            order._action_confirm()
        self.assertEqual(order.state, "draft")

    def test_sudo_bypasses(self):
        order = self._new_order()
        order.sudo().action_confirm()
        self.assertEqual(order.state, "sale")

    def test_not_blocked_without_flag(self):
        self.profile.node_line_ids.write({"enforce_server": False})
        order = self._new_order()
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_not_blocked_when_profile_inactive(self):
        self.profile.active = False
        order = self._new_order()
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_other_user_not_blocked(self):
        order = self.env["sale.order"].with_user(self.env.ref("base.user_admin")).create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})],
        })
        order.action_confirm()
        self.assertEqual(order.state, "sale")
