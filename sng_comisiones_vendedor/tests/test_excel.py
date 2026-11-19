# -*- coding: utf-8 -*-
"""Pruebas del libro de Excel del estado de comisiones (lógica pura, sin base
de datos).

Corren con Odoo (``--test-tags /sng_comisiones_vendedor``) y también solas:
    python tests/test_excel.py
"""
import datetime
import importlib.util
import io
import pathlib
import unittest

import openpyxl

try:
    from odoo.tests import BaseCase as Base, tagged
    from odoo.addons.sng_comisiones_vendedor.models import cruces, libro_excel
except ImportError:  # fuera de Odoo
    Base = unittest.TestCase

    def tagged(*_a):
        return lambda cls: cls

    def _cargar(nombre):
        ruta = pathlib.Path(__file__).resolve().parents[1] / 'models' / ('%s.py' % nombre)
        spec = importlib.util.spec_from_file_location(nombre, ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo
    cruces = _cargar('cruces')
    libro_excel = _cargar('libro_excel')

YO, OTRO = 10, 20
GF, PROTIRE = 1, 2
# Cada compañía con su propio cuadro, y un cuadro de grupo que junta las dos.
C_GF, C_PROTIRE, GRUPO = 101, 102, 7
CUADROS = {GF: {'id': C_GF, 'nombre': 'GF'}, PROTIRE: {'id': C_PROTIRE, 'nombre': 'PROTIRE'}}
TRAMOS = {C_GF: [(0.0, 0.0), (12e6, 2.75)], C_PROTIRE: [(0.0, 0.0), (12e6, 2.75)],
          GRUPO: [(0.0, 0.0), (12e6, 2.75), (20e6, 3.0), (25e6, 3.5), (35e6, 4.0)]}
HOJAS = ['Resumen', 'Reportados', 'Anulados', 'Registrados por otro',
         'Comisión de otro', 'Sin comisión', 'Reversos']


def pago(pid, **k):
    datos = {
        'id': pid, 'nombre': 'PBNK/%05d' % pid, 'recibo': '%06d' % pid, 'fecha': '2026-10-%02d' % (pid % 28 + 1),
        'fecha_confirmacion': '2026-10-%02d' % (pid % 28 + 1), 'cliente': 'Cliente %s' % pid,
        'compania_id': GF, 'compania': 'GF', 'monto': 1000.0, 'estado': 'in_process', 'verificado': True,
        'de_app': True, 'vendedor_id': YO, 'vendedor': 'Yo', 'creado_por': 'RPC', 'observaciones': '',
        'facturas': ['F%s' % pid], 'dup_estado': '', 'monto_atipico': False, 'ia_estado': '', 'conciliado': True,
        'comision_de': {YO: 'Yo'}, 'anulado_por': '', 'anulado_el': '',
    }
    datos.update(k)
    return datos


def linea(pid, base, tipo='commission', **k):
    datos = {'payment_id': pid, 'compania_id': GF, 'line_type': tipo, 'base': base, 'ajuste': 0.0,
             'motivo_reverso': '', 'periodo_original': ''}
    datos.update(k)
    return datos


def estado_completo():
    """Un pago de cada caso: propio con comisión, anulado rehecho por menos
    plata, registrado por la oficina, con comisión de otro vendedor, sin
    comisión y un reverso."""
    propio = pago(1, monto=1130.0)
    anulado = pago(2, estado='canceled', monto=5000.0, anulado_por='Angela',
                   anulado_el='2026-10-05T10:30:00-06:00', comision_de={})
    rehecho = pago(3, monto=4000.0)
    oficina = pago(4, de_app=False, vendedor_id=False, creado_por='Call Center', monto=2260.0)
    de_otro = pago(5, comision_de={OTRO: 'Otro Vendedor'}, monto=700.0)
    sin_factura = pago(6, comision_de={}, conciliado=False, ia_estado='sin_match', monto=300.0)
    reversado = pago(7, fecha='2026-09-15', monto=900.0)
    pagos = [propio, anulado, rehecho, oficina, de_otro, sin_factura, reversado]
    lineas = [linea(1, 1000.0), linea(3, 3539.82), linea(4, 2000.0),
              linea(7, 0.0, tipo='reversal', ajuste=-23.5, motivo_reverso='unreconciled',
                    periodo_original='2026-09-01')]
    mensuales = [{'mensual_id': 1, 'cuadro_id': C_GF, 'cuadro': 'GF', 'salesperson_id': YO, 'vendedor': 'Yo',
                  'estado': 'closed', 'base': 6539.82, 'porcentaje': 2.75, 'comision': 156.35, 'ajustes': -23.5,
                  'companias': [{'compania_id': GF, 'compania': 'GF', 'cobrado': 7390.0, 'base': 6539.82,
                                 'comision': 179.85, 'ajustes': -23.5}]}]
    return cruces.armar_estado(
        YO, 'Yo Vendedor', '2026-10-01', mensuales, lineas, {p['id']: p for p in pagos},
        [1, 2, 3, 5, 6], TRAMOS, [], {2: rehecho}, generado='2026-11-16T14:10:52-06:00', cuadros=CUADROS)


def abrir(estado):
    return openpyxl.load_workbook(io.BytesIO(libro_excel.generar(estado)))


def filas(hoja):
    """Filas de datos de una hoja de cruce como dicts {encabezado: valor}; la
    fila «Total» va aparte."""
    valores = list(hoja.iter_rows(values_only=True))
    encabezados = valores[0]
    datos = [dict(zip(encabezados, v)) for v in valores[1:]]
    total = next((d for d in datos if d[encabezados[0]] == 'Total'), None)
    return [d for d in datos if d is not total], total


def texto(hoja):
    return [c for fila in hoja.iter_rows(values_only=True) for c in fila if c is not None]


@tagged('post_install', '-at_install')
class TestLibroExcel(Base):

    def test_una_hoja_por_cruce(self):
        self.assertEqual(abrir(estado_completo()).sheetnames, HOJAS)

    def test_resumen_identifica_vendedor_mes_y_totales(self):
        estado = estado_completo()
        celdas = texto(abrir(estado)['Resumen'])
        self.assertIn('Yo Vendedor', celdas)
        self.assertIn('octubre 2026', celdas)
        self.assertIn('16/11/2026 14:10', celdas)
        for monto in (6539.82, 156.35, -23.5):
            self.assertIn(monto, celdas)
        self.assertIn('Cerrado', celdas)

    def test_resumen_trae_cantidad_y_monto_de_cada_cruce(self):
        estado = estado_completo()
        valores = list(abrir(estado)['Resumen'].iter_rows(values_only=True))
        por_nombre = {v[0]: v for v in valores if v[0]}
        for nombre, clave in (('Reportados', 'reportados'), ('Anulados', 'anulados'),
                              ('Registrados por otro', 'registrados_por_otro'),
                              ('Comisión de otro', 'comision_de_otro'),
                              ('Sin comisión', 'sin_comision'), ('Reversos', 'reversos')):
            grupo = estado['cruces'][clave]
            self.assertEqual(por_nombre[nombre][1], grupo['cantidad'], nombre)
            self.assertAlmostEqual(por_nombre[nombre][2], grupo['monto'], places=2, msg=nombre)

    def test_cada_hoja_trae_todos_los_pagos_y_su_total(self):
        estado = estado_completo()
        libro = abrir(estado)
        for nombre, clave in zip(HOJAS[1:], ('reportados', 'anulados', 'registrados_por_otro',
                                             'comision_de_otro', 'sin_comision', 'reversos')):
            grupo = estado['cruces'][clave]
            datos, total = filas(libro[nombre])
            self.assertEqual(len(datos), grupo['cantidad'], nombre)
            self.assertEqual([d['Pago'] for d in datos], [p['nombre'] for p in grupo['pagos']], nombre)
            self.assertAlmostEqual(total['Monto'], grupo['monto'], places=2, msg=nombre)

    def test_reportados_con_fecha_base_y_clase(self):
        datos, total = filas(abrir(estado_completo())['Reportados'])
        propio = next(d for d in datos if d['Pago'] == 'PBNK/00001')
        self.assertEqual(propio['Fecha'], datetime.datetime(2026, 10, 2))
        self.assertEqual(propio['Recibo'], '000001')
        self.assertEqual(propio['Monto'], 1130.0)
        self.assertEqual(propio['Base comisión'], 1000.0)
        self.assertEqual(propio['Situación'], 'Verificado')
        self.assertEqual(propio['Registrado por'], 'Yo')
        self.assertEqual(propio['Facturas'], 'F1')
        self.assertEqual(next(d for d in datos if d['Pago'] == 'PBNK/00002')['Situación'], 'Anulado')
        self.assertAlmostEqual(total['Base comisión'], 4539.82, places=2)

    def test_pago_sin_numero_se_identifica_por_su_id(self):
        # Un pago en borrador, o anulado sin asiento, no tiene número en Odoo.
        borrador = pago(9, nombre='', estado='draft', comision_de={})
        estado = cruces.armar_estado(YO, 'Yo', '2026-10-01', [], [], {9: borrador}, [9], TRAMOS, [], {})
        datos, _total = filas(abrir(estado)['Reportados'])
        self.assertEqual(datos[0]['Pago'], 'Sin número (id 9)')

    def test_anulado_rehecho_muestra_el_reemplazo_y_la_diferencia(self):
        datos, _total = filas(abrir(estado_completo())['Anulados'])
        self.assertEqual(len(datos), 1)
        fila = datos[0]
        self.assertEqual(fila['Clase'], 'Rehecho')
        self.assertEqual(fila['Anuló'], 'Angela')
        self.assertEqual(fila['Anulado el'], datetime.datetime(2026, 10, 5))
        self.assertEqual(fila['Pago que lo reemplaza'], 'PBNK/00003')
        self.assertEqual(fila['Monto del reemplazo'], 4000.0)
        self.assertEqual(fila['Diferencia'], -1000.0)

    def test_registrados_por_otro_dice_quien(self):
        estado = estado_completo()
        libro = abrir(estado)
        datos, total = filas(libro['Registrados por otro'])
        self.assertEqual(datos[0]['Registrado por'], 'Oficina · Call Center')
        self.assertEqual(total['Base comisión'], 2000.0)
        self.assertIn('Oficina · Call Center', texto(libro['Resumen']))

    def test_comision_de_otro_dice_de_quien(self):
        datos, _total = filas(abrir(estado_completo())['Comisión de otro'])
        self.assertEqual(datos[0]['Comisión de'], 'Otro Vendedor')

    def test_sin_comision_dice_el_motivo(self):
        datos, _total = filas(abrir(estado_completo())['Sin comisión'])
        self.assertEqual(datos[0]['Motivo'], 'Sin factura ligada (no se encontró la factura)')

    def test_reversos_con_mes_original_y_ajuste(self):
        datos, total = filas(abrir(estado_completo())['Reversos'])
        self.assertEqual(datos[0]['Motivo'], 'Pago desconciliado de la factura')
        self.assertEqual(datos[0]['Mes original'], 'septiembre 2026')
        self.assertEqual(datos[0]['Ajuste'], -23.5)
        self.assertEqual(total['Ajuste'], -23.5)

    def test_mes_abierto_muestra_proyeccion_y_siguiente_tramo(self):
        mensuales = [{'mensual_id': 1, 'cuadro_id': C_GF, 'cuadro': 'GF', 'salesperson_id': YO, 'vendedor': 'Yo',
                      'estado': 'draft', 'base': 11.5e6, 'porcentaje': 0.0, 'comision': 0.0, 'ajustes': 0.0,
                      'companias': []}]
        pendientes = [{'payment_id': 1, 'compania_id': GF, 'compania': 'GF', 'salesperson_id': YO,
                       'vendedor': 'Yo', 'base': 1e6, 'en_mes': True}]
        estado = cruces.armar_estado(YO, 'Yo', '2026-11-01', mensuales, [], {1: pago(1, comision_de={})},
                                     [1], TRAMOS, pendientes, {}, cuadros=CUADROS)
        celdas = texto(abrir(estado)['Resumen'])
        self.assertIn('Pendiente (estimado)', celdas)
        self.assertIn(1e6, celdas)                # en proceso
        self.assertIn(12.5e6, celdas)             # base proyectada
        self.assertIn(343750.0, celdas)           # comisión proyectada al 2.75 %
        self.assertIn('Faltan ₡500,000.00 para 2.75 %', celdas)

    def test_resumen_de_grupo_dice_el_cuadro_y_desglosa_por_compania(self):
        mensuales = [{
            'mensual_id': 99, 'cuadro_id': GRUPO, 'cuadro': 'Grupo', 'salesperson_id': YO, 'vendedor': 'Yo',
            'estado': 'draft', 'base': 29144491.09, 'porcentaje': 3.5, 'comision': 1020057.19, 'ajustes': 0.0,
            'companias': [
                {'compania_id': GF, 'compania': 'GF', 'cobrado': 3467028.70, 'base': 3068166.99,
                 'comision': 107385.84, 'ajustes': 0.0},
                {'compania_id': PROTIRE, 'compania': 'Protire', 'cobrado': 29466246.23, 'base': 26076324.10,
                 'comision': 912671.34, 'ajustes': 0.0}]}]
        estado = cruces.armar_estado(YO, 'Yo', '2026-11-01', mensuales, [], {}, [], TRAMOS, [], {},
                                     cuadros={GF: {'id': GRUPO, 'nombre': 'Grupo'},
                                              PROTIRE: {'id': GRUPO, 'nombre': 'Grupo'}})
        valores = list(abrir(estado)['Resumen'].iter_rows(values_only=True))
        encabezado = next(v for v in valores if v[0] == 'Cuadro' and v[1] == 'Vendedor')
        comision = valores[valores.index(encabezado) + 1]
        self.assertEqual((comision[0], comision[3], comision[4], comision[5]), ('Grupo', 29144491.09, 3.5, 1020057.19))
        self.assertIn('Faltan ₡5,855,508.91 para 4 %', comision)
        inicio = valores.index(next(v for v in valores if v[0] == 'Por compañía'))
        self.assertEqual(valores[inicio + 1][:6], ('Cuadro', 'Compañía', 'Cobrado', 'Base', 'Comisión', 'Ajustes'))
        self.assertEqual(valores[inicio + 2][:6], ('Grupo', 'GF', 3467028.70, 3068166.99, 107385.84, 0))
        self.assertEqual(valores[inicio + 3][:6], ('Grupo', 'Protire', 29466246.23, 26076324.10, 912671.34, 0))

    def test_sin_desglose_no_hay_tabla_por_compania(self):
        estado = cruces.armar_estado(YO, 'Yo', '2026-10-01', [], [], {}, [], TRAMOS, [], {})
        self.assertNotIn('Por compañía', texto(abrir(estado)['Resumen']))

    def test_siguiente_tramo_solo_en_mes_abierto(self):
        falta = {'minimo': 12e6, 'porcentaje': 2.75, 'falta': 500000.0}
        texto_tramo = libro_excel.siguiente_tramo_texto
        self.assertEqual(texto_tramo({'estado': 'draft', 'siguiente_tramo': falta}), 'Faltan ₡500,000.00 para 2.75 %')
        self.assertEqual(texto_tramo({'estado': 'draft', 'siguiente_tramo': None}), 'Tramo máximo')
        # En un mes cerrado el tramo ya no cambia: no es «tramo máximo».
        self.assertEqual(texto_tramo({'estado': 'closed', 'siguiente_tramo': None}), '')

    def test_mes_cerrado_no_dice_tramo_maximo(self):
        self.assertNotIn('Tramo máximo', texto(abrir(estado_completo())['Resumen']))

    def test_sin_movimientos_genera_las_hojas_vacias(self):
        estado = cruces.armar_estado(YO, 'Yo', '2026-10-01', [], [], {}, [], TRAMOS, [], {})
        libro = abrir(estado)
        self.assertEqual(libro.sheetnames, HOJAS)
        for nombre in HOJAS[1:]:
            datos, total = filas(libro[nombre])
            self.assertEqual(datos, [])
            self.assertEqual(total['Monto'], 0)


if __name__ == '__main__':
    unittest.main()
