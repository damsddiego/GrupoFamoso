# -*- coding: utf-8 -*-
"""Pruebas de las reglas de los cruces (lógica pura, sin base de datos).

Corren con Odoo (``--test-tags /sng_comisiones_vendedor``) y también solas:
    python tests/test_cruces.py
"""
import importlib.util
import pathlib
import unittest

try:
    from odoo.tests import BaseCase as Base, tagged
    from odoo.addons.sng_comisiones_vendedor.models import cruces
except ImportError:  # fuera de Odoo
    Base = unittest.TestCase

    def tagged(*_a):
        return lambda cls: cls
    _ruta = pathlib.Path(__file__).resolve().parents[1] / 'models' / 'cruces.py'
    _spec = importlib.util.spec_from_file_location('cruces', _ruta)
    cruces = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(cruces)

YO, OTRO = 10, 20
GF, PROTIRE = 1, 2
TRAMOS = {GF: [(0.0, 0.0), (12e6, 2.75), (20e6, 3.0), (30e6, 3.5)],
          PROTIRE: [(0.0, 0.0), (12e6, 2.75), (20e6, 3.0), (30e6, 3.5)]}


def pago(pid, **k):
    datos = {
        'id': pid, 'nombre': 'PBNK/%05d' % pid, 'recibo': '%06d' % pid, 'fecha': '2026-11-%02d' % (pid % 28 + 1),
        'fecha_confirmacion': '', 'cliente': 'Cliente %s' % pid, 'compania_id': GF, 'compania': 'GF',
        'monto': 1000.0, 'estado': 'in_process', 'verificado': True, 'de_app': True,
        'vendedor_id': YO, 'vendedor': 'Yo', 'creado_por': 'RPC', 'observaciones': '', 'facturas': ['F1'],
        'dup_estado': '', 'monto_atipico': False, 'ia_estado': '', 'conciliado': True,
        'comision_de': {YO: 'Yo'}, 'anulado_por': '', 'anulado_el': '',
    }
    datos.update(k)
    return datos


def linea(pid, base, tipo='commission', **k):
    datos = {'payment_id': pid, 'compania_id': GF, 'line_type': tipo, 'base': base, 'ajuste': 0.0,
             'motivo_reverso': '', 'periodo_original': ''}
    datos.update(k)
    return datos


def estado(pagos, reportados, lineas=(), mensuales=None, pendientes=(), reemplazos=None):
    if mensuales is None:
        base = sum(l['base'] for l in lineas if l['line_type'] == 'commission')
        mensuales = [{'compania_id': GF, 'compania': 'GF', 'estado': 'draft', 'base': base,
                      'porcentaje': 0.0, 'comision': 0.0, 'ajustes': 0.0}]
    return cruces.armar_estado(
        YO, 'Yo', '2026-11-01', mensuales, list(lineas), {p['id']: p for p in pagos},
        reportados, TRAMOS, list(pendientes), reemplazos or {})


@tagged('post_install', '-at_install')
class TestCruces(Base):

    def test_tramo_y_siguiente(self):
        self.assertEqual(cruces.tramo(TRAMOS, GF, 11e6), (0.0, {'minimo': 12e6, 'porcentaje': 2.75, 'falta': 1e6}))
        pct, sig = cruces.tramo(TRAMOS, GF, 25e6)
        self.assertEqual(pct, 3.0)
        self.assertEqual(sig['falta'], 5e6)
        self.assertEqual(cruces.tramo(TRAMOS, GF, 40e6), (3.5, None))

    def test_reportados_por_estado(self):
        pagos = [pago(1), pago(2, verificado=False), pago(3, estado='draft'),
                 pago(4, estado='canceled'), pago(5, estado='rejected'), pago(6, estado='paid')]
        r = estado(pagos, [p['id'] for p in pagos])['cruces']['reportados']
        self.assertEqual(r['cantidad'], 6)
        self.assertEqual(r['por_estado'], {'verificado': 2, 'sin_verificar': 1, 'no_aplicado': 1,
                                           'anulado': 1, 'rechazado': 1})
        self.assertEqual(r['monto'], 6000.0)

    def test_anulados_feria_rehecho_y_sin_reemplazo(self):
        feria = pago(1, estado='canceled', observaciones='Venta de feria: orden S50100 (aplicar...)')
        rehecho = pago(2, estado='canceled', anulado_por='Angela')
        nuevo = pago(3)
        solo = pago(4, estado='rejected')
        e = estado([feria, rehecho, nuevo, solo], [1, 2, 3, 4], reemplazos={2: nuevo})
        a = e['cruces']['anulados']
        clases = {p['id']: p['clase'] for p in a['pagos']}
        self.assertEqual(clases, {1: 'feria', 2: 'rehecho', 4: 'sin_reemplazo'})
        self.assertEqual((a['rehechos'], a['feria'], a['sin_reemplazo']), (1, 1, 1))
        p2 = next(p for p in a['pagos'] if p['id'] == 2)
        self.assertEqual(p2['reemplazo']['nombre'], nuevo['nombre'])
        self.assertEqual(p2['anulado_por'], 'Angela')

    def test_registrado_por_otro_agrupa_por_quien(self):
        oficina = pago(1, de_app=False, creado_por='Call Center', vendedor_id=False)
        de_otro = pago(2, vendedor_id=OTRO, vendedor='Otro')
        sin_vend = pago(3, vendedor_id=False)
        mio = pago(4)
        lineas = [linea(1, 100.0), linea(1, 50.0), linea(2, 200.0), linea(3, 10.0), linea(4, 999.0)]
        r = estado([oficina, de_otro, sin_vend, mio], [4], lineas)['cruces']['registrados_por_otro']
        self.assertEqual(r['cantidad'], 3)
        self.assertEqual(r['base'], 360.0)
        quien = {(q['tipo'], q['nombre']): (q['cantidad'], q['base']) for q in r['por_quien']}
        self.assertEqual(quien, {('oficina', 'Oficina · Call Center'): (1, 150.0),
                                 ('vendedor', 'Otro'): (1, 200.0),
                                 ('app_sin_vendedor', 'App sin vendedor'): (1, 10.0)})

    def test_comision_de_otro_y_sin_comision(self):
        de_otro = pago(1, comision_de={OTRO: 'Otro'})
        sin_factura = pago(2, comision_de={}, conciliado=False, ia_estado='sin_match')
        duplicado = pago(3, comision_de={}, dup_estado='sospecha')
        en_proceso = pago(4, comision_de={})
        sin_vend = pago(5, comision_de={})
        anulado = pago(6, comision_de={}, estado='canceled')
        pend = [{'payment_id': 4, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': YO, 'base': 800.0},
                {'payment_id': 5, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': None, 'base': 0.0}]
        e = estado([de_otro, sin_factura, duplicado, en_proceso, sin_vend, anulado], [1, 2, 3, 4, 5, 6],
                   pendientes=pend)
        c = e['cruces']
        self.assertEqual([p['id'] for p in c['comision_de_otro']['pagos']], [1])
        self.assertEqual(c['comision_de_otro']['pagos'][0]['comision_a'], 'Otro')
        motivos = {p['id']: p['motivo'] for p in c['sin_comision']['pagos']}
        self.assertEqual(set(motivos), {2, 3, 4, 5})
        self.assertIn('no se encontró', motivos[2])
        self.assertIn('duplicado', motivos[3])
        self.assertIn('En proceso', motivos[4])
        self.assertIn('no tiene vendedor', motivos[5])
        self.assertEqual(e['resumen'][0]['en_proceso'], 800.0)

    def test_proyeccion_cruza_tramo(self):
        lineas = [linea(1, 11.5e6)]
        mens = [{'compania_id': GF, 'compania': 'GF', 'estado': 'draft', 'base': 11.5e6,
                 'porcentaje': 0.0, 'comision': 0.0, 'ajustes': -100.0}]
        pend = [{'payment_id': 2, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': YO, 'base': 1e6}]
        r = estado([pago(1), pago(2, comision_de={})], [1, 2], lineas, mens, pend)['resumen'][0]
        self.assertTrue(r['estimado'])
        self.assertEqual(r['siguiente_tramo']['falta'], 0.5e6)
        self.assertEqual(r['proyeccion']['porcentaje'], 2.75)
        self.assertEqual(r['proyeccion']['comision'], round(12.5e6 * 0.0275 - 100.0, 2))

    def test_mes_cerrado_no_proyecta_y_pendiente_crea_compania(self):
        mens = [{'compania_id': GF, 'compania': 'GF', 'estado': 'closed', 'base': 21e6,
                 'porcentaje': 3.0, 'comision': 630000.0, 'ajustes': 0.0}]
        pend = [{'payment_id': 2, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': YO, 'base': 5.0},
                {'payment_id': 3, 'compania_id': PROTIRE, 'compania': 'PROTIRE', 'salesperson_id': YO, 'base': 7.0}]
        e = estado([pago(2, comision_de={}), pago(3, comision_de={}, compania_id=PROTIRE)], [2, 3],
                   [linea(9, 21e6)], mens, pend)
        res = {r['compania_id']: r for r in e['resumen']}
        self.assertIsNone(res[GF]['proyeccion'])
        self.assertFalse(res[GF]['estimado'])
        self.assertEqual(res[PROTIRE]['en_proceso'], 7.0)
        self.assertEqual(e['totales']['comision'], 630000.0)

    def test_reversos(self):
        lineas = [linea(1, 0.0, 'reversal', ajuste=-598.0, motivo_reverso='canceled', periodo_original='2026-10-01')]
        r = estado([pago(1, estado='canceled')], [], lineas)['cruces']['reversos']
        self.assertEqual(r['cantidad'], 1)
        self.assertEqual(r['ajuste'], -598.0)
        self.assertEqual(r['pagos'][0]['motivo'], 'Pago anulado')
        self.assertEqual(r['pagos'][0]['periodo_original'], '2026-10-01')


if __name__ == '__main__':
    unittest.main()
