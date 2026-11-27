# -*- coding: utf-8 -*-
import io

import openpyxl

from odoo.tests import BaseCase, tagged

from ..report import sell_in_out_xlsx


def _datos():
    return {
        'companias': 'SAASA',
        'periodo': '01/07/2026 al 31/08/2026',
        'corte': 'Datos de Odoo al 01/09/2026 08:00, hora de Costa Rica.',
        'meses': ['2026-07', '2026-08'],
        'filas': [
            {'compania': 'SAASA', 'codigo': 'A1', 'descripcion': 'Aceite 1L', 'base': 'MINERAL', 'pilar': 'MCO',
             'volumen': 1.0, 'stock': 10.0, 'transito': 5.0, 'bodega': 100.0,
             'in_mes': {'2026-07': 50.0, '2026-08': 20.0}, 'out_mes': {'2026-07': 8.0, '2026-08': 12.0},
             'proveedores': 'GF'},
            {'compania': 'SAASA', 'codigo': 'A2', 'descripcion': 'Aceite estañón', 'base': 'MINERAL', 'pilar': 'MCO',
             'volumen': 208.0, 'stock': 2.0, 'transito': 0.0, 'bodega': 0.0,
             'in_mes': {'2026-08': 3.0}, 'out_mes': {'2026-08': 1.0},
             'proveedores': 'Motul'},
            {'compania': 'SAASA', 'codigo': 'C1', 'descripcion': 'Limpiador 400 ml', 'base': '', 'pilar': 'MC CARE',
             'volumen': 0.4, 'stock': 30.0, 'transito': 0.0, 'bodega': 0.0,
             'in_mes': {}, 'out_mes': {'2026-07': 10.0},
             'proveedores': ''},
        ],
    }


@tagged('post_install', '-at_install')
class TestSellInOutXlsx(BaseCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        contenido = sell_in_out_xlsx.generar(_datos())
        # data_only: se leen los valores guardados junto a cada fórmula.
        cls.libro = openpyxl.load_workbook(io.BytesIO(contenido), data_only=True)

    def _filas(self, hoja):
        return list(self.libro[hoja].iter_rows(min_row=sell_in_out_xlsx.FIRST + 1, values_only=True))

    def test_hojas(self):
        self.assertEqual(self.libro.sheetnames, ['BASE DATOS', 'POR MES', 'TABLA', 'Notas'])
        self.assertIn('SAASA', self.libro['BASE DATOS']['A1'].value)
        self.assertIn('01/07/2026 al 31/08/2026', self.libro['BASE DATOS']['A1'].value)

    def test_base_datos(self):
        filas = self._filas('BASE DATOS')
        self.assertEqual(len(filas), 4)  # 3 productos + total
        a1, a2, c1, total = filas
        # código, base, pilar, descripción, volumen, stock, tránsito, bodega, total, litros,
        # sell in u, sell in L, sell out u, sell out L, proveedor, compañía
        self.assertEqual(a1[:4], ('A1', 'MINERAL', 'MCO', 'Aceite 1L'))
        self.assertEqual(a1[4:14], (1, 10, 5, 100, 115, 115, 70, 70, 20, 20))
        self.assertEqual(a2[8:14], (2, 416, 3, 624, 1, 208))
        self.assertEqual(c1[8:14], (30, 12, 0, 0, 10, 4))
        self.assertEqual(total[0], 'Total')
        self.assertEqual(total[5:14], (42, 5, 100, 147, 543, 73, 694, 31, 232))

    def test_por_mes(self):
        filas = self._filas('POR MES')
        self.assertEqual(len(filas), 7)  # 3 productos × 2 meses + total
        self.assertEqual(filas[0][:2], ('Julio 2026', 'A1'))
        self.assertEqual(filas[0][6:10], (50, 50, 8, 8))
        self.assertEqual(filas[4][:2], ('Agosto 2026', 'A2'))
        self.assertEqual(filas[4][6:10], (3, 624, 1, 208))
        self.assertEqual(filas[-1][6:10], (73, 694, 31, 232))

    def test_tabla_por_pilar_y_base(self):
        filas = self._filas('TABLA')
        self.assertEqual(len(filas), 3)  # MC CARE/(sin base), MCO/MINERAL, total
        care, mco, total = filas
        self.assertEqual(care[:3], ('MC CARE', '(sin base)', 12))
        # inventario, in jul, in ago, in total, out jul, out ago, out total
        self.assertEqual(mco[:2], ('MCO', 'MINERAL'))
        self.assertEqual(mco[2:], (531, 50, 644, 694, 8, 220, 228))
        self.assertEqual(total[2:], (543, 50, 644, 694, 12, 220, 232))
