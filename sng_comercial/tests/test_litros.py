# -*- coding: utf-8 -*-
from odoo.tests import BaseCase, tagged

from ..litros import litros_desde_texto


@tagged('post_install', '-at_install')
class TestLitros(BaseCase):

    def test_valores_reales_del_atributo_volumen(self):
        casos = {
            '1L': 1.0,
            '5L': 5.0,
            '20L': 20.0,
            '208L': 208.0,
            '60 L': 60.0,
            '400ml': 0.4,
            '500ml': 0.5,
            'LIQ FRENO 250 ml': 0.25,
            'LIQ FRENO 500 ml': 0.5,
            '1.2': 1.2,
            'ESTAÑÓN': 208.0,
            'ESTAÑONES': 208.0,
        }
        for texto, litros in casos.items():
            self.assertAlmostEqual(litros_desde_texto(texto), litros, places=3, msg=texto)

    def test_lo_que_no_es_volumen_da_cero(self):
        for texto in ('BOMBA', 'BOQUILLA', 'CAJA NEGRA', 'EXHIBIDOR', 'LONAS', '0', '', None):
            self.assertEqual(litros_desde_texto(texto), 0.0, texto)

    def test_variantes_de_escritura(self):
        self.assertEqual(litros_desde_texto('4 lts'), 4.0)
        self.assertEqual(litros_desde_texto('1 Litro'), 1.0)
        self.assertEqual(litros_desde_texto('0,946 L'), 0.946)
        self.assertEqual(litros_desde_texto('estanon'), 208.0)
        # Un número pegado a otra palabra no es un volumen.
        self.assertEqual(litros_desde_texto('Modelo 300'), 0.0)
