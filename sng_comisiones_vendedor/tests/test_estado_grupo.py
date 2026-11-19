# -*- coding: utf-8 -*-
import json
from datetime import date

from odoo.tests import new_test_user, tagged

from odoo.addons.sng_sales_commission_payment.tests.common import ComisionGrupoCase


@tagged('post_install', '-at_install')
class TestEstadoGrupo(ComisionGrupoCase):
    """El estado del vendedor con un cuadro de varias compañías: un solo
    resumen por comisión, con el desglose por compañía."""

    def setUp(self):
        super().setUp()
        self.grupo = self._cuadro('Grupo', self.cia_a | self.cia_b, date(2031, 3, 1))
        self.mensual = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        self._linea(self.mensual, self.cia_a, 26076324.10)
        self._linea(self.mensual, self.cia_b, 3068166.99)
        self.mensual._recompute_commission()
        self.oficina = new_test_user(
            self.env, login='oficina_estado_grupo_prueba',
            groups='base.group_user,sales_commission_omax.group_sales_commission_user')

    def test_un_resumen_por_comision_con_desglose(self):
        estado = self.env['sng.comision.estado'].with_user(self.oficina).obtener_estado(
            self.vendedor.id, '2031-03-15')
        json.dumps(estado)  # la app lo recibe por JSON-RPC
        (r,) = estado['resumen']
        self.assertEqual((r['mensual_id'], r['cuadro_id'], r['cuadro']),
                         (self.mensual.id, self.grupo.id, 'Grupo'))
        self.assertEqual([c['compania_id'] for c in r['companias']], [self.cia_a.id, self.cia_b.id])
        self.assertAlmostEqual(r['companias'][0]['base'], 26076324.10, places=2)
        self.assertAlmostEqual(r['companias'][1]['comision'], 107385.84, places=2)
        self.assertAlmostEqual(r['base'], 29144491.09, places=2)
        self.assertEqual(r['porcentaje'], 3.5)
        self.assertAlmostEqual(r['comision'], 1020057.19, places=2)
        self.assertEqual(r['siguiente_tramo'], {'minimo': 35000000.0, 'porcentaje': 4.0, 'falta': 5855508.91})
        self.assertAlmostEqual(estado['totales']['base'], 29144491.09, places=2)

    def test_asistente_muestra_el_cuadro_y_sus_companias(self):
        asistente = self.env['sng.comision.estado.wizard'].with_user(self.oficina).create({
            'vendedor_id': self.vendedor.id, 'periodo': '2031-03-15'})
        asistente.action_consultar()
        html = asistente.resumen_html
        self.assertIn('Grupo', html)
        self.assertIn('Por compañía', html)
        self.assertIn(self.cia_b.name, html)
        self.assertIn('Faltan ₡5,855,508.91 para 4 %', html)
