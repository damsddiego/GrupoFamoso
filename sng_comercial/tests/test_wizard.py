# -*- coding: utf-8 -*-
import io

import openpyxl

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..report import sell_in_out_xlsx
from .common import ComercialCommon


@tagged('post_install', '-at_install')
class TestSellWizard(ComercialCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aceite = cls._producto('Aceite asistente 5L', 'COM-WIZ-1', cls.pilar, cls.base, cls.vol_5)
        cls._recibir(cls.aceite, 100, '2031-03-10')
        cls._recibir(cls.aceite, 40, '2031-04-10')
        cls._facturar(cls.aceite, 25, '2031-04-20')
        cls._recibir(cls.aceite, 999, '2031-06-01')  # fuera del periodo
        cls.env['stock.quant']._update_available_quantity(cls.aceite, cls._stock_location(cls.company), 7)
        cls.env.flush_all()
        cls.wizard = cls.env['sng.comercial.sell.wizard'].create({
            'date_from': '2031-03-01',
            'date_to': '2031-04-30',
            'company_ids': [(6, 0, cls.company.ids)],
        })

    def _fila(self, datos):
        return next(fila for fila in datos['filas'] if fila['codigo'] == 'COM-WIZ-1')

    def test_datos_del_periodo(self):
        datos = self.wizard._datos()
        self.assertEqual(datos['meses'], ['2031-03', '2031-04'])
        self.assertEqual(datos['periodo'], '01/03/2031 al 30/04/2031')
        fila = self._fila(datos)
        self.assertEqual(fila['in_mes'], {'2031-03': 100.0, '2031-04': 40.0})
        self.assertEqual(fila['out_mes'], {'2031-03': 0.0, '2031-04': 25.0})
        self.assertEqual((fila['pilar'], fila['base'], fila['volumen']), ('PILAR TEST', 'BASE TEST', 5.0))
        self.assertEqual(fila['proveedores'], 'Proveedor comercial test')
        # 7 puestos a mano + 140 recibidos en el periodo + 999 recibidos después.
        self.assertEqual(fila['stock'], 1146.0)

    def test_excel_cuadra_con_los_datos(self):
        nombre, contenido = self.wizard._excel()
        self.assertEqual(nombre, 'Sell in - Sell out 2031-03-01 a 2031-04-30.xlsx')
        libro = openpyxl.load_workbook(io.BytesIO(contenido), data_only=True)
        self.assertEqual(libro.sheetnames, ['BASE DATOS', 'POR MES', 'TABLA', 'Notas'])
        fila = next(
            f for f in libro['BASE DATOS'].iter_rows(min_row=sell_in_out_xlsx.FIRST + 1, values_only=True)
            if f[0] == 'COM-WIZ-1')
        # sell in unidades / litros, sell out unidades / litros
        self.assertEqual(fila[10:14], (140, 700, 25, 125))

    def test_descarga_y_analisis(self):
        accion = self.wizard.action_descargar_excel()
        self.assertEqual(accion['type'], 'ir.actions.act_url')
        adjunto = self.env['ir.attachment'].search([
            ('res_model', '=', self.wizard._name), ('res_id', '=', self.wizard.id)])
        self.assertEqual(len(adjunto), 1)
        self.assertIn('/web/content/%d' % adjunto.id, accion['url'])
        # Una segunda descarga reemplaza la anterior.
        self.wizard.action_descargar_excel()
        self.assertFalse(adjunto.exists())

        analisis = self.wizard.action_ver_analisis()
        self.assertEqual(analisis['res_model'], 'sng.comercial.sell.report')
        self.assertIn(('date', '>=', self.wizard.date_from), analisis['domain'])

    def test_fechas_invertidas(self):
        with self.assertRaises(ValidationError):
            self.wizard.write({'date_from': '2031-05-01'})
