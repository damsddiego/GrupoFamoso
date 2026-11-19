# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ComisionGrupoCase


@tagged('post_install', '-at_install')
class TestCuadro(ComisionGrupoCase):
    """Qué cuadro rige para una compañía en un mes, y qué tramo da."""

    def test_rige_el_cuadro_mas_reciente(self):
        viejo = self._cuadro('A sola', self.cia_a, date(2031, 1, 1))
        grupo = self._cuadro('Grupo', self.cia_a | self.cia_b, date(2031, 3, 1))
        self.assertEqual(self.Scheme._get_for_company(self.cia_a, date(2031, 2, 1)), viejo)
        self.assertEqual(self.Scheme._get_for_company(self.cia_a, date(2031, 3, 1)), grupo)
        self.assertEqual(self.Scheme._get_for_company(self.cia_b, date(2031, 5, 1)), grupo)

    def test_cuadro_archivado_cede_al_anterior(self):
        viejo = self._cuadro('A sola', self.cia_a, date(2031, 1, 1))
        grupo = self._cuadro('Grupo', self.cia_a | self.cia_b, date(2031, 3, 1))
        grupo.active = False
        self.assertEqual(self.Scheme._get_for_company(self.cia_a, date(2031, 4, 1)), viejo)
        # Tampoco rige si quien pregunta viene de una pantalla que muestra archivados.
        Scheme = self.Scheme.with_context(active_test=False)
        self.assertEqual(Scheme._get_for_company(self.cia_a, date(2031, 4, 1)), viejo)

    def test_cuadro_archivado_no_bloquea_otro_con_su_misma_vigencia(self):
        archivado = self._cuadro('Uno', self.cia_a, date(2031, 1, 1))
        archivado.active = False
        nuevo = self.Scheme.with_context(active_test=False).create({
            'name': 'Dos', 'company_ids': [(6, 0, self.cia_a.ids)], 'date_start': date(2031, 1, 1)})
        self.assertTrue(nuevo.active)

    def test_no_dos_cuadros_misma_compania_y_vigencia(self):
        self._cuadro('Uno', self.cia_a, date(2031, 1, 1))
        with self.assertRaises(ValidationError):
            self._cuadro('Dos', self.cia_a | self.cia_b, date(2031, 1, 1))

    def test_vigencia_se_normaliza_al_dia_uno(self):
        self.assertEqual(self._cuadro('X', self.cia_a, date(2031, 1, 17)).date_start, date(2031, 1, 1))

    def test_companias_de_un_cuadro_comparten_moneda(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        otra = self.env['res.company'].create({'name': 'Compañía en dólares de prueba', 'currency_id': usd.id})
        with self.assertRaises(ValidationError):
            self._cuadro('Mixto', self.cia_a | otra, date(2031, 1, 1))

    def test_tramo_por_cuadro(self):
        grupo = self._cuadro('Grupo', self.cia_a | self.cia_b, date(2031, 3, 1))
        Tier = self.env['sng.commission.tier']
        self.assertEqual(Tier.get_percentage_for_amount(29144491.09, grupo), 3.5)
        self.assertEqual(Tier.get_percentage_for_amount(25000000.00, grupo), 3.5)
        self.assertEqual(Tier.get_percentage_for_amount(24999999.99, grupo), 3.0)
        self.assertEqual(Tier.get_percentage_for_amount(11999999.99, grupo), 0.0)
