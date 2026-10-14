from odoo.tests.common import TransactionCase


class TestSngReturnSalesperson(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({
            "name": "Otra compañía vendedor",
        })
        cls.env.user.write({
            "groups_id": [(4, cls.env.ref("sng_return.group_sng_return_supervisor").id)],
            "company_ids": [(4, cls.other_company.id)],
        })
        cls.seller_a = cls.env["res.partner"].create({
            "name": "Vendedor A",
            "is_salesperson": True,
        })
        cls.seller_b = cls.env["res.partner"].create({
            "name": "Vendedor B",
            "is_salesperson": True,
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Cliente con vendedor",
            "customer_rank": 1,
        })
        cls.partner.with_company(cls.company).assigned_salesperson_id = cls.seller_a
        cls.partner.with_company(cls.other_company).assigned_salesperson_id = cls.seller_b
        cls.reason = cls.env["sng.return.reason"].create({
            "name": "Motivo vendedor",
        })

    def _create_return(self, company, partner=None):
        return self.env["sng.return"].with_company(company).create({
            "partner_id": (partner or self.partner).id,
            "reason_id": self.reason.id,
            "company_id": company.id,
        })

    def test_vendedor_asignado_por_compania(self):
        self.assertEqual(self._create_return(self.company).salesperson_id, self.seller_a)
        self.assertEqual(self._create_return(self.other_company).salesperson_id, self.seller_b)

    def test_vendedor_del_contacto_padre(self):
        contact = self.env["res.partner"].create({
            "name": "Contacto del cliente",
            "parent_id": self.partner.id,
            "type": "contact",
        })
        record = self._create_return(self.company, partner=contact)
        self.assertEqual(record.salesperson_id, self.seller_a)

    def test_cambio_en_cliente_no_reescribe_devolucion(self):
        record = self._create_return(self.company)
        self.partner.with_company(self.company).assigned_salesperson_id = self.seller_b
        record.invalidate_recordset()
        self.assertEqual(record.salesperson_id, self.seller_a)

    def test_vendedor_editable_y_agrupable(self):
        record = self._create_return(self.company)
        record.salesperson_id = self.seller_b
        groups = self.env["sng.return"].read_group(
            [("id", "=", record.id)], ["salesperson_id"], ["salesperson_id"]
        )
        self.assertEqual(groups[0]["salesperson_id"][0], self.seller_b.id)
