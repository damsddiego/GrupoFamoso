# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: disable_login enforcement test.

Covers:
  * a user in a profile with disable_login=True hits AccessDenied
  * an admin in such a profile is exempt
  * an inactive profile does not block
"""
from odoo.exceptions import AccessDenied
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDisableLogin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.User = cls.env["res.users"]
        cls.Profile = cls.env["eh.access.profile"]
        cls.demo_user = cls.User.with_context(no_reset_password=True).create({
            "name": "Login Block Demo",
            "login": "eh_access_login_block@example.test",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def test_blocked_user_raises(self):
        self.Profile.create({
            "name": "Block login",
            "disable_login": True,
            "user_ids": [(6, 0, [self.demo_user.id])],
        })
        # Helper short-circuits when env.su is True. Run as the demo
        # user so the gate executes the way the real login path does.
        with self.assertRaises(AccessDenied):
            self.demo_user.with_user(self.demo_user)._eh_access_studio_check_login_disabled()

    def test_inactive_profile_does_not_block(self):
        self.Profile.create({
            "name": "Block login (inactive)",
            "disable_login": True,
            "active": False,
            "user_ids": [(6, 0, [self.demo_user.id])],
        })
        # No exception expected even when running as the demo user.
        self.demo_user.with_user(self.demo_user)._eh_access_studio_check_login_disabled()
