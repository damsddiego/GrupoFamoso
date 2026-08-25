# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: YAML import / export round-trip test.

Covers:
  * an exported profile reimports to an equivalent record
  * lines and toggles survive the round trip
  * import is idempotent: re-running import on the same payload does
    not create duplicates of an existing profile name
"""
import base64

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestYamlWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.User = cls.env["res.users"]
        cls.Profile = cls.env["eh.access.profile"]
        cls.Wizard = cls.env["eh.access.yaml.wizard"]
        cls.IrModel = cls.env["ir.model"]
        cls.IrField = cls.env["ir.model.fields"]

        cls.demo_user = cls.User.with_context(no_reset_password=True).create({
            "name": "YAML Demo",
            "login": "eh_access_yaml_demo@example.test",
        })
        cls.partner_model = cls.IrModel._get("res.partner")
        cls.comment_field = cls.IrField.search([
            ("model", "=", "res.partner"),
            ("name", "=", "comment"),
        ], limit=1)

    def _make_full_profile(self, name="Round-trip"):
        return self.Profile.create({
            "name": name,
            "user_ids": [(6, 0, [self.demo_user.id])],
            "hide_export": True,
            "hide_chatter": True,
            "field_line_ids": [(0, 0, {
                "model_id": self.partner_model.id,
                "field_ids": [(6, 0, [self.comment_field.id])],
                "invisible": True,
            })],
            "model_line_ids": [(0, 0, {
                "model_id": self.partner_model.id,
                "restrict_create": True,
                "restrict_export": True,
            })],
            "node_line_ids": [(0, 0, {
                "model_id": self.partner_model.id,
                "kind": "button",
                "target_name": "action_view_orders",
                "target_label": "View Orders",
            })],
            "domain_line_ids": [(0, 0, {
                "model_id": self.partner_model.id,
                "read_right": True,
                "write_right": True,
                "apply_filter": True,
                "domain": '[("user_id", "=", "__uid__")]',
            })],
        })

    def _export(self, profile):
        wiz = self.Wizard.create({
            "mode": "export",
            "profile_ids": [(6, 0, [profile.id])],
        })
        wiz.action_export()
        return base64.b64decode(wiz.payload).decode("utf-8")

    def _import(self, text):
        wiz = self.Wizard.create({
            "mode": "import",
            "payload": base64.b64encode(text.encode("utf-8")),
        })
        wiz.action_import()
        return wiz

    def test_export_then_import_yields_equivalent_profile(self):
        original = self._make_full_profile(name="Source RT")
        text = self._export(original)
        self.assertIn("Source RT", text)
        self.assertIn("hide_export", text)
        self.assertIn("__uid__", text)

        # Delete the original then reimport to a clean state.
        original.unlink()
        self._import(text)
        clone = self.Profile.search([("name", "=", "Source RT")], limit=1)
        self.assertTrue(clone, "imported profile should exist")
        self.assertTrue(clone.hide_export)
        self.assertTrue(clone.hide_chatter)
        self.assertEqual(len(clone.field_line_ids), 1)
        self.assertTrue(clone.field_line_ids.invisible)
        self.assertEqual(len(clone.model_line_ids), 1)
        self.assertTrue(clone.model_line_ids.restrict_create)
        self.assertEqual(len(clone.node_line_ids), 1)
        self.assertEqual(clone.node_line_ids.target_name, "action_view_orders")
        self.assertEqual(len(clone.domain_line_ids), 1)
        self.assertTrue(clone.domain_line_ids.apply_filter)
        self.assertIn("__uid__", clone.domain_line_ids.domain)
        self.assertIn(self.demo_user, clone.user_ids)

    def test_import_is_idempotent_by_name(self):
        original = self._make_full_profile(name="Idempotent RT")
        text = self._export(original)
        self._import(text)
        self._import(text)
        matches = self.Profile.search([("name", "=", "Idempotent RT")])
        self.assertEqual(len(matches), 1, "no duplicate profiles on re-import")
