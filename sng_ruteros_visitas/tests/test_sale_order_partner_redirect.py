# -*- coding: utf-8 -*-
import json

from odoo.tests.common import TransactionCase

from odoo.addons.sng_ruteros_pagos.models.res_partner import (
    SNG_PARAM_CLIENTES,
)


class TestSaleOrderPartnerRedirect(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente vigente de prueba',
        })
        cls.stale_partner_id = 2147483000
        cls.env['ir.config_parameter'].sudo().set_param(
            SNG_PARAM_CLIENTES,
            json.dumps({str(cls.stale_partner_id): cls.partner.id}),
        )

    def test_create_redirects_all_sale_order_partner_fields(self):
        order = self.env['sale.order'].create({
            'partner_id': self.stale_partner_id,
            'partner_invoice_id': self.stale_partner_id,
            'partner_shipping_id': self.stale_partner_id,
        })

        self.assertEqual(order.partner_id, self.partner)
        self.assertEqual(order.partner_invoice_id, self.partner)
        self.assertEqual(order.partner_shipping_id, self.partner)

    def test_write_redirects_stale_shipping_partner(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        order.write({'partner_shipping_id': self.stale_partner_id})

        self.assertEqual(order.partner_shipping_id, self.partner)
