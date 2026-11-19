# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ComisionGrupoCase


@tagged('post_install', '-at_install')
class TestCierreCuadro(ComisionGrupoCase):
    """El mes se cierra una vez por cuadro; la factura y el análisis saben que
    un mensual puede juntar varias compañías."""

    def setUp(self):
        super().setUp()
        self.grupo = self._cuadro('Grupo', self.cia_a | self.cia_b, date(2031, 3, 1))

    def test_cerrar_genera_pendientes_de_cada_compania(self):
        m = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        with patch.object(type(self.Monthly), '_sng_generate_pending', autospec=True,
                          return_value=self.env['account.payment']) as generar:
            m.action_close()
        self.assertEqual({c.args[1] for c in generar.call_args_list}, {self.cia_a, self.cia_b})
        self.assertEqual({c.args[2:] for c in generar.call_args_list}, {(date(2031, 3, 1), date(2031, 3, 31))})
        self.assertEqual(m.state, 'closed')

    def test_asistente_cierra_todos_los_borradores_del_cuadro(self):
        otro = self.env['res.partner'].create({'name': 'Otro vendedor de prueba', 'is_salesperson': True})
        m1 = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        m2 = self.Monthly._get_or_create(otro, self.cia_b, date(2031, 3, 1))
        wiz = self.env['sng.close.commission.wiz'].create({'period': date(2031, 3, 15), 'scheme_id': self.grupo.id})
        self.assertEqual(wiz.pending_count, 2)
        wiz.action_close_month()
        self.assertEqual((m1 | m2).mapped('state'), ['closed', 'closed'])

    def test_reporte_consolidado_toma_los_mensuales_del_cuadro(self):
        m = self.Monthly._get_or_create(self.vendedor, self.cia_b, date(2031, 3, 1))
        wiz = self.env['sng.commission.report.wiz'].create({'period': date(2031, 3, 15), 'scheme_id': self.grupo.id})
        self.assertEqual(wiz._get_monthlies(), m)
        self.assertEqual(wiz.monthly_count, 1)

    def test_factura_rechaza_mensual_de_varias_companias(self):
        m = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        self._linea(m, self.cia_a, 26076324.10)
        m._recompute_commission()
        m.write({'closed': True})
        wiz = self.env['sng.create.commission.bill.wiz'].with_context(active_ids=m.ids).create({})
        with self.assertRaisesRegex(UserError, 'varias compañías'):
            wiz.action_create_bills()

    def test_analisis_busca_el_mes_original_por_compania(self):
        self._cuadro('A sola', self.cia_a, date(2031, 1, 1))
        febrero = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 2, 1))
        self._linea(febrero, self.cia_a, 13000000.00)
        febrero._recompute_commission()
        febrero.write({'closed': True})
        marzo = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        self.assertEqual(marzo._sng_original_percentage(self.cia_a, date(2031, 2, 1)), 2.75)
        self.assertIsNone(marzo._sng_original_percentage(self.cia_b, date(2031, 2, 1)))
