# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import patch

from odoo.tests import tagged

from .common import ComisionGrupoCase


@tagged('post_install', '-at_install')
class TestMensualCuadro(ComisionGrupoCase):
    """Un mensual por vendedor, mes y cuadro: junta los cobros de todas las
    compañías del cuadro y saca el tramo de la base sumada."""

    def setUp(self):
        super().setUp()
        self.grupo = self._cuadro('Grupo', self.cia_a | self.cia_b, date(2031, 3, 1))

    def test_dos_companias_un_solo_mensual(self):
        m_a = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        m_b = self.Monthly._get_or_create(self.vendedor, self.cia_b, date(2031, 3, 1))
        self.assertEqual(m_a, m_b)
        self.assertEqual(m_a.scheme_id, self.grupo)
        self.assertFalse(m_a.company_id)
        self._linea(m_a, self.cia_a, 26076324.10)
        self._linea(m_a, self.cia_b, 3068166.99)
        m_a._recompute_commission()
        self.assertAlmostEqual(m_a.base_amount, 29144491.09, places=2)
        self.assertEqual(m_a.percentage, 3.5)
        self.assertAlmostEqual(m_a.commission_amount, 1020057.19, places=2)

    def test_antes_de_la_vigencia_va_por_compania(self):
        sola = self._cuadro('A sola', self.cia_a, date(2031, 1, 1))
        m = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 2, 1))
        self.assertEqual(m.scheme_id, sola)
        self.assertEqual(m.company_id, self.cia_a)

    def test_cobro_tardio_rueda_al_mensual_del_grupo(self):
        self._cuadro('A sola', self.cia_a, date(2031, 1, 1))
        febrero = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 2, 1))
        febrero.write({'closed': True})
        self.assertEqual(
            self.Monthly._get_open_period(self.vendedor, self.cia_a, date(2031, 2, 1)), date(2031, 3, 1))
        marzo = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        self.assertEqual(marzo.scheme_id, self.grupo)

    def test_reverso_salta_mes_de_grupo_cerrado(self):
        self._cuadro('A sola', self.cia_a, date(2031, 1, 1))
        febrero = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 2, 1))
        linea = self._linea(febrero, self.cia_a, 13000000.00)
        febrero._recompute_commission()          # 2.75 %
        febrero.write({'closed': True})
        marzo = self.Monthly._get_or_create(self.vendedor, self.cia_b, date(2031, 3, 1))
        marzo.write({'closed': True})
        with patch.object(type(self.env['account.payment']), '_sng_confirmation_today',
                          return_value=date(2031, 3, 20)):
            linea._create_reversals('canceled')
        reverso = linea.reversal_line_ids
        self.assertEqual(reverso.monthly_id.period, date(2031, 4, 1))
        self.assertEqual(reverso.monthly_id.scheme_id, self.grupo)
        self.assertAlmostEqual(reverso.commission_adjustment, -357500.00, places=2)

    def test_mes_cerrado_sigue_cerrado_si_se_archiva_su_cuadro(self):
        """Marzo cerró en el cuadro del grupo. Si después se archiva el grupo
        y vuelve a regir el cuadro anterior, un cobro tardío de marzo no abre
        un marzo nuevo: rueda a abril."""
        self._cuadro('A sola', self.cia_a, date(2031, 1, 1))
        marzo = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        marzo.write({'closed': True})
        self.grupo.active = False
        self.assertEqual(
            self.Monthly._get_open_period(self.vendedor, self.cia_a, date(2031, 3, 1)), date(2031, 4, 1))
        # Otro vendedor, sin mes cerrado, sí puede abrir marzo.
        otro = self.env['res.partner'].create({'name': 'Otro vendedor de prueba', 'is_salesperson': True})
        self.assertEqual(
            self.Monthly._get_open_period(otro, self.cia_a, date(2031, 3, 1)), date(2031, 3, 1))

    def test_compania_sin_cuadro_no_genera_linea(self):
        otra = self.env['res.company'].create({'name': 'Compañía sin cuadro de prueba'})
        self.assertFalse(self.Monthly._get_open_period(self.vendedor, otra, date(2031, 3, 1)))
        self.assertFalse(self.Monthly._get_or_create(self.vendedor, otra, date(2031, 3, 1)))
