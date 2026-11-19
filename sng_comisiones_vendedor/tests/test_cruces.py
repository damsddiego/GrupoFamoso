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
# Cada compañía con su propio cuadro, y un cuadro de grupo que junta las dos.
C_GF, C_PROTIRE, GRUPO = 101, 102, 7
CUADROS = {GF: {'id': C_GF, 'nombre': 'GF'}, PROTIRE: {'id': C_PROTIRE, 'nombre': 'PROTIRE'}}
CUADROS_GRUPO = {GF: {'id': GRUPO, 'nombre': 'Grupo'}, PROTIRE: {'id': GRUPO, 'nombre': 'Grupo'}}
TRAMOS = {C_GF: [(0.0, 0.0), (12e6, 2.75), (20e6, 3.0), (30e6, 3.5)],
          C_PROTIRE: [(0.0, 0.0), (12e6, 2.75), (20e6, 3.0), (30e6, 3.5)],
          GRUPO: [(0.0, 0.0), (12e6, 2.75), (20e6, 3.0), (25e6, 3.5), (35e6, 4.0)]}
MENSUAL_GRUPO = {
    'mensual_id': 99, 'cuadro_id': GRUPO, 'cuadro': 'Grupo', 'salesperson_id': 10, 'vendedor': 'Yo',
    'estado': 'draft', 'base': 29144491.09, 'porcentaje': 3.5, 'comision': 1020057.19, 'ajustes': 0.0,
    'companias': [
        {'compania_id': GF, 'compania': 'GF', 'cobrado': 3467028.70, 'base': 3068166.99,
         'comision': 107385.84, 'ajustes': 0.0},
        {'compania_id': PROTIRE, 'compania': 'Protire', 'cobrado': 29466246.23, 'base': 26076324.10,
         'comision': 912671.34, 'ajustes': 0.0},
    ]}


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


def mensual(**k):
    datos = {'mensual_id': 1, 'cuadro_id': C_GF, 'cuadro': 'GF', 'estado': 'draft', 'base': 0.0,
             'porcentaje': 0.0, 'comision': 0.0, 'ajustes': 0.0, 'companias': []}
    datos.update(k)
    return datos


def estado(pagos, reportados, lineas=(), mensuales=None, pendientes=(), reemplazos=None):
    if mensuales is None:
        base = sum(l['base'] for l in lineas if l['line_type'] == 'commission')
        mensuales = [mensual(base=base)]
    return cruces.armar_estado(
        YO, 'Yo', '2026-11-01', mensuales, list(lineas), {p['id']: p for p in pagos},
        reportados, TRAMOS, list(pendientes), reemplazos or {}, cuadros=CUADROS)


@tagged('post_install', '-at_install')
class TestCruces(Base):

    def test_tramo_y_siguiente(self):
        self.assertEqual(cruces.tramo(TRAMOS, C_GF, 11e6), (0.0, {'minimo': 12e6, 'porcentaje': 2.75, 'falta': 1e6}))
        pct, sig = cruces.tramo(TRAMOS, C_GF, 25e6)
        self.assertEqual(pct, 3.0)
        self.assertEqual(sig['falta'], 5e6)
        self.assertEqual(cruces.tramo(TRAMOS, C_GF, 40e6), (3.5, None))

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
        mens = [mensual(base=11.5e6, ajustes=-100.0)]
        pend = [{'payment_id': 2, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': YO, 'base': 1e6}]
        r = estado([pago(1), pago(2, comision_de={})], [1, 2], lineas, mens, pend)['resumen'][0]
        self.assertTrue(r['estimado'])
        self.assertEqual(r['siguiente_tramo']['falta'], 0.5e6)
        self.assertEqual(r['proyeccion']['porcentaje'], 2.75)
        self.assertEqual(r['proyeccion']['comision'], round(12.5e6 * 0.0275 - 100.0, 2))

    def test_mes_cerrado_no_proyecta_y_pendiente_crea_resumen(self):
        mens = [mensual(estado='closed', base=21e6, porcentaje=3.0, comision=630000.0)]
        pend = [{'payment_id': 2, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': YO, 'base': 5.0},
                {'payment_id': 3, 'compania_id': PROTIRE, 'compania': 'PROTIRE', 'salesperson_id': YO, 'base': 7.0}]
        e = estado([pago(2, comision_de={}), pago(3, comision_de={}, compania_id=PROTIRE)], [2, 3],
                   [linea(9, 21e6)], mens, pend)
        res = {r['cuadro_id']: r for r in e['resumen']}
        self.assertIsNone(res[C_GF]['proyeccion'])
        self.assertIsNone(res[C_GF]['siguiente_tramo'])
        self.assertFalse(res[C_GF]['estimado'])
        self.assertEqual(res[C_PROTIRE]['en_proceso'], 7.0)
        self.assertEqual((res[C_PROTIRE]['cuadro'], res[C_PROTIRE]['mensual_id']), ('PROTIRE', False))
        self.assertEqual(e['totales']['comision'], 630000.0)
        self.assertEqual(e['totales']['en_proceso'], 7.0)  # lo de GF rueda al mes siguiente

    def test_reversos(self):
        lineas = [linea(1, 0.0, 'reversal', ajuste=-598.0, motivo_reverso='canceled', periodo_original='2026-10-01')]
        r = estado([pago(1, estado='canceled')], [], lineas)['cruces']['reversos']
        self.assertEqual(r['cantidad'], 1)
        self.assertEqual(r['ajuste'], -598.0)
        self.assertEqual(r['pagos'][0]['motivo'], 'Pago anulado')
        self.assertEqual(r['pagos'][0]['periodo_original'], '2026-10-01')

    def test_contactos_duplicados_cuentan_como_yo(self):
        DUP = 11
        p_dup = pago(1, vendedor_id=DUP, vendedor='YO DUPLICADO', comision_de={DUP: 'YO DUPLICADO'})
        mens = [mensual(mensual_id=1, salesperson_id=YO, vendedor='Yo', base=100.0),
                mensual(mensual_id=2, salesperson_id=DUP, vendedor='YO DUPLICADO', base=50.0)]
        e = cruces.armar_estado({YO, DUP}, 'Yo', '2026-11-01', mens, [linea(1, 50.0)], {1: p_dup}, [1],
                                TRAMOS, [], {})
        c = e['cruces']
        self.assertEqual(c['registrados_por_otro']['cantidad'], 0)
        self.assertEqual(c['comision_de_otro']['cantidad'], 0)
        self.assertEqual(c['reportados']['pagos'][0]['registrado_por']['tipo'], 'yo')
        self.assertEqual(len(e['resumen']), 2)  # cada contacto conserva su mensual y su tramo
        self.assertEqual(e['vendedor']['ids'], [YO, DUP])
        self.assertEqual(cruces.normalizar_nombre('  Juan   pérez '), 'JUAN PÉREZ')

    def test_anulado_duplicado_tiene_prioridad_sobre_rehecho(self):
        anulado = pago(1, estado='canceled', comision_de={})
        original = pago(2)
        e = cruces.armar_estado(YO, 'Yo', '2026-11-01', [], [], {1: anulado, 2: original}, [1, 2], TRAMOS, [],
                                {1: original}, duplicados={1: original})
        a = e['cruces']['anulados']
        self.assertEqual(a['pagos'][0]['clase'], 'duplicado')
        self.assertEqual((a['duplicados'], a['rehechos']), (1, 0))

    def test_motivo_fuera_de_mes_y_de_otro_vendedor(self):
        fuera = pago(1, comision_de={}, fecha_confirmacion='2026-12-02')
        ajeno = pago(2, comision_de={})
        pend = [{'payment_id': 1, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': YO, 'base': 0.0,
                 'en_mes': False},
                {'payment_id': 2, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': OTRO,
                 'vendedor': 'Otro', 'base': 0.0, 'en_mes': True}]
        e = estado([fuera, ajeno], [1, 2], pendientes=pend)
        motivos = {p['id']: p['motivo'] for p in e['cruces']['sin_comision']['pagos']}
        self.assertIn('02/12/2026', motivos[1])
        self.assertEqual(motivos[2], 'La factura es de otro vendedor: Otro')
        self.assertEqual(e['resumen'][0]['en_proceso'], 0.0)

    def test_un_resumen_por_mensual_de_grupo(self):
        e = cruces.armar_estado(YO, 'Yo', '2026-11-01', [MENSUAL_GRUPO], [], {}, [], TRAMOS, [], {},
                                cuadros=CUADROS_GRUPO)
        (r,) = e['resumen']
        self.assertEqual((r['mensual_id'], r['cuadro_id'], r['cuadro']), (99, GRUPO, 'Grupo'))
        self.assertEqual([c['compania_id'] for c in r['companias']], [GF, PROTIRE])
        self.assertNotIn('compania_id', r)
        self.assertNotIn('compania', r)
        self.assertEqual(r['siguiente_tramo'], {'minimo': 35e6, 'porcentaje': 4.0, 'falta': 5855508.91})

    def test_pendiente_de_otra_compania_suma_al_mismo_resumen(self):
        pendiente = {'payment_id': 5, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': YO,
                     'vendedor': 'Yo', 'base': 6000000.0, 'en_mes': True}
        e = cruces.armar_estado(YO, 'Yo', '2026-11-01', [MENSUAL_GRUPO], [], {5: pago(5)}, [], TRAMOS,
                                [pendiente], {}, cuadros=CUADROS_GRUPO)
        (r,) = e['resumen']
        self.assertEqual(r['en_proceso'], 6000000.0)
        self.assertEqual(r['proyeccion']['base'], 35144491.09)
        self.assertEqual(r['proyeccion']['porcentaje'], 4.0)
        self.assertEqual(r['proyeccion']['comision'], 1405779.64)

    def test_pendiente_de_compania_sin_cuadro_no_cuenta(self):
        pendiente = {'payment_id': 5, 'compania_id': 99, 'compania': 'Sin cuadro', 'salesperson_id': YO,
                     'vendedor': 'Yo', 'base': 500.0, 'en_mes': True}
        e = estado([pago(5, comision_de={}, compania_id=99)], [5], pendientes=[pendiente])
        self.assertEqual(e['totales']['en_proceso'], 0.0)
        self.assertEqual(len(e['resumen']), 1)


if __name__ == '__main__':
    unittest.main()
