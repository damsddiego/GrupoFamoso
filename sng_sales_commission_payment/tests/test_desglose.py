# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests import tagged

from .common import ComisionGrupoCase


@tagged('post_install', '-at_install')
class TestDesglose(ComisionGrupoCase):
    """El mensual de un cuadro de varias compañías dice cuánto viene de cada una."""

    def setUp(self):
        super().setUp()
        self._cuadro('Grupo', self.cia_a | self.cia_b, date(2031, 3, 1))
        self.m = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        self._linea(self.m, self.cia_a, 26076324.10)
        self._linea(self.m, self.cia_b, 3068166.99)
        self.m._recompute_commission()
        self.usuario = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Usuario de comisiones de una compañía',
            'login': 'prueba_comisiones_una_cia',
            'company_id': self.cia_a.id,
            'company_ids': [(6, 0, self.cia_a.ids)],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('sales_commission_omax.group_sales_commission_user').id,
            ])],
        })

    def test_desglose_por_compania(self):
        filas = self.m._get_company_breakdown()
        self.assertEqual([f['company'] for f in filas], [self.cia_a, self.cia_b])
        self.assertAlmostEqual(filas[0]['base'], 26076324.10, places=2)
        self.assertAlmostEqual(filas[0]['payment_amount'], 26076324.10, places=2)
        self.assertAlmostEqual(filas[0]['commission'], 912671.34, places=2)
        self.assertAlmostEqual(filas[1]['commission'], 107385.84, places=2)
        self.assertAlmostEqual(sum(f['base'] for f in filas), self.m.base_amount, places=2)

    def test_reverso_va_en_los_ajustes_de_su_compania(self):
        reverso = self._linea(self.m, self.cia_b, 0.0, tipo='reversal')
        reverso.write({'payment_amount': -1000.0, 'commission_adjustment': -35.0})
        filas = self.m._get_company_breakdown()
        self.assertAlmostEqual(filas[0]['adjustment'], 0.0, places=2)
        self.assertAlmostEqual(filas[1]['adjustment'], -35.0, places=2)
        # Lo cobrado y la base son solo de las líneas de comisión.
        self.assertAlmostEqual(filas[1]['payment_amount'], 3068166.99, places=2)

    def test_usuario_de_una_compania_ve_el_desglose(self):
        m = self.m.with_user(self.usuario).with_context(allowed_company_ids=self.cia_a.ids)
        self.assertAlmostEqual(m.read(['base_amount'])[0]['base_amount'], 29144491.09, places=2)
        self.assertEqual(len(m._get_company_breakdown()), 2)
        self.assertIn(self.cia_b.name, m.company_breakdown_html)
