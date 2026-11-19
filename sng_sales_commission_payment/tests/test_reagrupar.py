# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ComisionGrupoCase


@tagged('post_install', '-at_install')
class TestReagrupar(ComisionGrupoCase):
    """Al crear un cuadro de grupo, los mensuales en borrador que estaban por
    compañía se juntan en uno solo, sin perder líneas."""

    def setUp(self):
        super().setUp()
        self._cuadro('A sola', self.cia_a, date(2031, 1, 1))
        self._cuadro('B sola', self.cia_b, date(2031, 1, 1))
        self.m_a = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        self.m_b = self.Monthly._get_or_create(self.vendedor, self.cia_b, date(2031, 3, 1))
        self._linea(self.m_a, self.cia_a, 26076324.10)
        self._linea(self.m_b, self.cia_b, 3068166.99)
        (self.m_a | self.m_b)._recompute_commission()
        self.grupo = self._cuadro('Grupo', self.cia_a | self.cia_b, date(2031, 3, 1))

    def _de_marzo(self):
        return self.Monthly.search([
            ('salesperson_id', '=', self.vendedor.id), ('period', '=', date(2031, 3, 1))])

    def test_antes_de_reagrupar_cada_compania_tiene_su_tramo(self):
        self.assertEqual((self.m_a.percentage, self.m_b.percentage), (3.5, 0.0))

    def test_junta_los_borradores_sin_perder_lineas(self):
        lineas = (self.m_a | self.m_b).mapped('line_ids')
        res = self.Monthly._sng_regroup_open()
        grupo = self._de_marzo()
        self.assertEqual(len(grupo), 1)
        self.assertEqual(grupo.scheme_id, self.grupo)
        self.assertFalse(grupo.company_id)
        self.assertEqual(grupo.line_ids, lineas)
        self.assertAlmostEqual(grupo.base_amount, 29144491.09, places=2)
        self.assertEqual(grupo.percentage, 3.5)
        self.assertAlmostEqual(grupo.commission_amount, 1020057.19, places=2)
        self.assertEqual((res['moved_lines'], res['created_monthlies'], res['removed_monthlies']), (2, 1, 2))
        self.assertEqual(res['skipped'], [])

    def test_simulacion_no_guarda(self):
        res = self.Monthly._sng_regroup_open(dry_run=True)
        self.assertEqual((res['moved_lines'], res['created_monthlies'], res['removed_monthlies']), (2, 1, 2))
        self.assertEqual(self.m_a.exists().scheme_id.name, 'A sola')
        self.assertEqual(len(self.m_a.line_ids), 1)
        self.assertEqual(len(self._de_marzo()), 2)

    def test_repetir_no_cambia_nada(self):
        self.Monthly._sng_regroup_open()
        res = self.Monthly._sng_regroup_open()
        self.assertEqual((res['moved_lines'], res['created_monthlies'], res['removed_monthlies']), (0, 0, 0))

    def test_no_toca_al_vendedor_con_un_mes_cerrado(self):
        self.m_b.write({'closed': True})
        res = self.Monthly._sng_regroup_open()
        self.assertEqual(res['moved_lines'], 0)
        self.assertEqual(len(res['skipped']), 1)
        self.assertEqual(res['skipped'][0]['salesperson'], self.vendedor)
        self.assertEqual(res['skipped'][0]['period'], date(2031, 3, 1))
        self.assertEqual(len(self.m_a.line_ids), 1)
        self.assertEqual(self.m_a.scheme_id.name, 'A sola')

    def test_meses_anteriores_a_la_vigencia_no_se_mueven(self):
        febrero = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 2, 1))
        self._linea(febrero, self.cia_a, 1000000.00)
        self.Monthly._sng_regroup_open()
        self.assertEqual(febrero.exists().scheme_id.name, 'A sola')
        self.assertEqual(len(febrero.line_ids), 1)

    def test_borra_borradores_vacios_del_cuadro_anterior(self):
        otro = self.env['res.partner'].create({'name': 'Otro vendedor de prueba', 'is_salesperson': True})
        self._cuadro('A vieja', self.cia_a, date(2030, 6, 1))
        vacio = self.Monthly.create({
            'salesperson_id': otro.id, 'period': date(2031, 3, 1), 'company_id': self.cia_a.id,
            'scheme_id': self.Scheme.search([('name', '=', 'A sola')]).id})
        vigente = self.Monthly._get_or_create(otro, self.cia_a, date(2031, 2, 1))  # febrero: rige «A sola»
        res = self.Monthly._sng_regroup_open()
        self.assertFalse(vacio.exists())
        self.assertTrue(vigente.exists())
        self.assertEqual(res['removed_monthlies'], 3)

    def test_cerrar_exige_reagrupar(self):
        with self.assertRaisesRegex(UserError, 'Reagrupar'):
            self.m_a.action_close()

    def test_boton_del_cuadro_reagrupa(self):
        self.grupo.action_regroup_open_months()
        self.assertEqual(self._de_marzo().scheme_id, self.grupo)
