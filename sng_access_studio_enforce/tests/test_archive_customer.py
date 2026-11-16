# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestArchiveCustomer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Archivar Demo",
            "login": "sng_archive_demo@example.test",
            "groups_id": [(6, 0, [
                cls.env.ref("sales_team.group_sale_manager").id,
                cls.env.ref("base.group_partner_manager").id,
            ])],
        })
        cls.admin = cls.env.ref("base.user_admin")
        cls.customer = cls.env["res.partner"].create({
            "name": "Cliente archivar", "is_company": True, "customer_rank": 1,
        })
        cls.contact = cls.env["res.partner"].create({
            "name": "Contacto del cliente", "parent_id": cls.customer.id,
        })
        cls.other = cls.env["res.partner"].create({"name": "No cliente"})

    def test_user_cannot_archive_customer(self):
        with self.assertRaises(AccessError):
            self.customer.with_user(self.user).action_archive()
        self.assertTrue(self.customer.active)

    def test_user_cannot_archive_by_write(self):
        with self.assertRaises(AccessError):
            self.customer.with_user(self.user).write({"active": False})
        self.assertTrue(self.customer.active)

    def test_user_cannot_archive_customer_contact(self):
        with self.assertRaises(AccessError):
            self.contact.with_user(self.user).action_archive()
        self.assertTrue(self.contact.active)

    def test_user_can_archive_non_customer(self):
        self.other.with_user(self.user).action_archive()
        self.assertFalse(self.other.active)

    def test_user_can_edit_customer(self):
        self.customer.with_user(self.user).write({"phone": "8888-8888"})
        self.assertEqual(self.customer.phone, "8888-8888")

    def test_admin_can_archive_customer(self):
        self.customer.with_user(self.admin).action_archive()
        self.assertFalse(self.customer.active)

    def test_sudo_bypasses(self):
        self.customer.with_user(self.user).sudo().action_archive()
        self.assertFalse(self.customer.active)

    def test_unarchive_not_blocked(self):
        self.customer.action_archive()
        self.customer.with_user(self.user).action_unarchive()
        self.assertTrue(self.customer.active)
