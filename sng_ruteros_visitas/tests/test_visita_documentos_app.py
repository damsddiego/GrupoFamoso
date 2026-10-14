# -*- coding: utf-8 -*-
import uuid

from odoo.tests.common import TransactionCase


class TestVisitaDocumentosApp(TransactionCase):
    """La app liga la visita a la orden o pago que creó; si ese documento ya
    no existe aquí (o es de otra compañía) la visita debe entrar igual, sin
    el documento, en vez de violar la FK y hacer que la app reintente."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente visita de prueba',
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'company_id': cls.company.id,
        })
        cls.id_inexistente = 2147483000
        cls.Visita = cls.env['sng.ruteros.visita']

    def _crear(self, **extra):
        vals = {
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'resultado': 'venta',
            'sng_uuid': 'test-%s' % uuid.uuid4(),
        }
        vals.update(extra)
        return self.Visita.create(vals)

    def test_orden_existente_se_conserva(self):
        visita = self._crear(sale_order_id=self.order.id)
        self.assertEqual(visita.sale_order_id, self.order)
        self.assertFalse(visita.sale_order_app_id)

    def test_orden_inexistente_no_bloquea_la_visita(self):
        visita = self._crear(sale_order_id=self.id_inexistente)
        self.assertTrue(visita.exists())
        self.assertFalse(visita.sale_order_id)
        self.assertEqual(visita.sale_order_app_id, self.id_inexistente)
        self.assertTrue(any(
            str(self.id_inexistente) in (m.body or '')
            for m in visita.message_ids))

    def test_pago_inexistente_no_bloquea_la_visita(self):
        visita = self._crear(resultado='cobro',
                             payment_id=self.id_inexistente)
        self.assertFalse(visita.payment_id)
        self.assertEqual(visita.payment_app_id, self.id_inexistente)

    def test_orden_de_otra_compania_se_desliga(self):
        otra = self.env['res.company'].create({'name': 'Otra cía visita'})
        orden_otra = self.env['sale.order'].with_company(otra).create({
            'partner_id': self.partner.id,
            'company_id': otra.id,
        })
        visita = self._crear(sale_order_id=orden_otra.id)
        self.assertFalse(visita.sale_order_id)
        self.assertEqual(visita.sale_order_app_id, orden_otra.id)
