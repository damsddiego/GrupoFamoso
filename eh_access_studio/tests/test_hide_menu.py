# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: hide-menu integration tests.

Covers:
  * search_fetch returns the hidden menu for an unaffected user
  * search_fetch drops the hidden menu for an affected user
  * the configuration menu is never hidden, even if listed
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHideMenu(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.demo_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Menu Demo",
            "login": "eh_access_menu_demo@example.test",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.unaffected_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Unaffected",
            "login": "eh_access_unaffected@example.test",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        # Pick a menu the standard base.group_user can see so the
        # "unaffected user still sees" assertion exercises our overlay
        # rather than Odoo's group-based menu visibility.
        cls.target_menu = cls.env.ref("mail.menu_root_discuss")
        cls.profile = cls.env["eh.access.profile"].create({
            "name": "Hide Settings",
            "user_ids": [(6, 0, [cls.demo_user.id])],
            "hidden_menu_ids": [(6, 0, [cls.target_menu.id])],
        })

    def _menu_ids_for(self, user):
        Menu = self.env["ir.ui.menu"].with_user(user)
        return set(Menu.search_fetch([], ["id"]).ids)

    def test_unaffected_user_still_sees_target_menu(self):
        self.assertIn(self.target_menu.id, self._menu_ids_for(self.unaffected_user))

    def test_affected_user_loses_target_menu(self):
        self.assertNotIn(self.target_menu.id, self._menu_ids_for(self.demo_user))

    def test_configuration_menu_always_visible(self):
        own_menu = self.env.ref("eh_access_studio.menu_eh_access_root")
        self.profile.write({
            "hidden_menu_ids": [(6, 0, [own_menu.id])],
        })
        # Demo user is not in the manager group, so they should not see
        # the menu via group ACL anyway. The test is really about admins
        # never being locked out, so we re-run with a manager.
        manager = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Manager",
            "login": "eh_access_manager_demo@example.test",
            "groups_id": [
                (6, 0, [
                    self.env.ref("base.group_user").id,
                    self.env.ref("eh_access_studio.group_eh_access_manager").id,
                ]),
            ],
        })
        self.profile.write({
            "user_ids": [(6, 0, [manager.id])],
        })
        self.assertIn(own_menu.id, self._menu_ids_for(manager))
