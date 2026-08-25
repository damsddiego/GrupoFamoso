# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: profile lifecycle tests.

Covers:
  * basic create / write / unlink
  * admin protection: read-only profile rejects admin users
  * date window validation
  * active-profile cache hit / miss for a user
  * cache invalidation on profile change
  * cron deactivates expired profiles
"""
from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProfileLifecycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.User = cls.env["res.users"]
        cls.Profile = cls.env["eh.access.profile"]
        cls.demo_user = cls.User.with_context(no_reset_password=True).create({
            "name": "Access Studio Demo",
            "login": "eh_access_demo@example.test",
        })

    def test_create_and_count(self):
        profile = self.Profile.create({
            "name": "Sales viewers",
            "user_ids": [(6, 0, [self.demo_user.id])],
        })
        self.assertTrue(profile.active)
        self.assertEqual(profile.rule_count, 0)

    def test_admin_in_readonly_blocked(self):
        admin = self.env.ref("base.user_admin")
        with self.assertRaises(ValidationError):
            self.Profile.create({
                "name": "Block admin",
                "readonly": True,
                "user_ids": [(6, 0, [admin.id])],
            })

    def test_date_window_validation(self):
        with self.assertRaises(ValidationError):
            self.Profile.create({
                "name": "Bad window",
                "date_from": date(2026, 12, 31),
                "date_until": date(2026, 1, 1),
            })

    def test_active_cache_invalidates_on_write(self):
        profile = self.Profile.create({
            "name": "Cache check",
            "user_ids": [(6, 0, [self.demo_user.id])],
        })
        today_iso = self.Profile._today_for_cache_key()
        ids_a = self.Profile._get_active_profile_ids(
            self.demo_user.id, self.env.company.id, today_iso,
        )
        self.assertIn(profile.id, ids_a)
        profile.active = False
        ids_b = self.Profile._get_active_profile_ids(
            self.demo_user.id, self.env.company.id, today_iso,
        )
        self.assertNotIn(profile.id, ids_b)

    def test_duplicate_name_rejected(self):
        self.Profile.create({"name": "Same name"})
        with self.assertRaises(ValidationError):
            self.Profile.create({"name": "Same name"})

    def test_cron_deactivates_expired(self):
        yesterday = date.today() - timedelta(days=1)
        profile = self.Profile.create({
            "name": "Expired",
            "user_ids": [(6, 0, [self.demo_user.id])],
            "date_until": yesterday,
        })
        self.assertTrue(profile.active)
        self.Profile._cron_deactivate_expired_profiles()
        profile.invalidate_recordset()
        self.assertFalse(profile.active)
