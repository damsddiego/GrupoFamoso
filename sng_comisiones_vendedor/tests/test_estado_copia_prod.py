# -*- coding: utf-8 -*-
"""Pruebas de ``obtener_estado`` contra datos reales de octubre de 2026.

Solo corren en una copia neutralizada de prod_gf y se saltan si esos datos
no existen:

    --test-tags /sng_comisiones_vendedor:TestEstadoCopiaProd
"""
import json
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

OCTUBRE = date(2026, 10, 1)
DANIEL = 9
HENRY = 24


@tagged('post_install', '-at_install', 'sng_copia_prod')
class TestEstadoCopiaProd(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usuario_app = new_test_user(
            cls.env, login='app_ruteros_prueba',
            groups='base.group_user,sng_comisiones_vendedor.group_comisiones_app')
        cls.Estado = cls.env['sng.comision.estado'].with_user(cls.usuario_app)

    def _estado(self, vendedor_id):
        if not self.env['sng.commission.monthly'].search_count([
                ('salesperson_id', '=', vendedor_id), ('period', '=', OCTUBRE), ('state', '!=', 'draft')]):
            self.skipTest('Sin el cierre de octubre 2026 de prod_gf en esta base.')
        return self.Estado.obtener_estado(vendedor_id, '2026-10-15')

    def test_resumen_cuadra_con_mensuales(self):
        for vendedor_id in (DANIEL, HENRY):
            estado = self._estado(vendedor_id)
            json.dumps(estado)  # la app lo recibe por JSON-RPC
            self.assertEqual(estado['periodo'], '2026-10-01')
            self.assertEqual(len(estado['periodos']), 7)
            for r in estado['resumen']:
                mensual = self.env['sng.commission.monthly'].browse(r['mensual_id'] or [])
                if mensual:
                    self.assertEqual(mensual.period, OCTUBRE)
                    self.assertEqual(r['cuadro_id'], mensual.scheme_id.id)
                    self.assertAlmostEqual(sum(c['base'] for c in r['companias']), r['base'], places=2)
                    self.assertAlmostEqual(r['base'], mensual.base_amount, places=2)
                    self.assertAlmostEqual(r['comision'], mensual.commission_amount, places=2)
                    self.assertFalse(r['estimado'])

    def test_cruces_coherentes(self):
        estado = self._estado(HENRY)
        c = estado['cruces']
        pe = c['reportados']['por_estado']
        self.assertEqual(sum(pe.values()), c['reportados']['cantidad'])
        self.assertEqual(c['anulados']['cantidad'], pe['anulado'] + pe['rechazado'])
        self.assertEqual(c['anulados']['cantidad'],
                         c['anulados']['rehechos'] + c['anulados']['duplicados']
                         + c['anulados']['feria'] + c['anulados']['sin_reemplazo'])
        self.assertTrue(all(p['registrado_por']['tipo'] != 'yo' for p in c['registrados_por_otro']['pagos']))

    def test_rechaza_quien_no_es_vendedor(self):
        with self.assertRaises(UserError):
            self.Estado.obtener_estado(self.env.company.partner_id.id)

    def test_sin_grupo_no_puede_consultar(self):
        sin_grupo = new_test_user(self.env, login='interno_sin_grupo', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.env['sng.comision.estado'].with_user(sin_grupo).obtener_estado(HENRY)
