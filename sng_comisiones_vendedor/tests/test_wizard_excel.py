# -*- coding: utf-8 -*-
import base64
import io

import openpyxl

from odoo.tests import TransactionCase, new_test_user, tagged

HOJAS = ['Resumen', 'Reportados', 'Anulados', 'Registrados por otro',
         'Comisión de otro', 'Sin comisión', 'Reversos']


@tagged('post_install', '-at_install')
class TestWizardExcel(TransactionCase):
    """El botón «Descargar Excel» del asistente de oficina."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.oficina = new_test_user(
            cls.env, login='oficina_comisiones_prueba',
            groups='base.group_user,sales_commission_omax.group_sales_commission_user')
        cls.vendedor = cls.env['res.partner'].create({
            'name': 'Vendedor Prueba Excel', 'is_salesperson': True})

    def _asistente(self):
        return self.env['sng.comision.estado.wizard'].with_user(self.oficina).create({
            'vendedor_id': self.vendedor.id, 'periodo': '2026-10-15'})

    def _adjuntos(self, asistente):
        return self.env['ir.attachment'].search([
            ('res_model', '=', asistente._name), ('create_uid', '=', self.oficina.id)])

    def test_descarga_el_libro_del_vendedor_y_mes(self):
        asistente = self._asistente()
        accion = asistente.action_descargar_excel()
        adjunto = self._adjuntos(asistente)
        self.assertEqual(len(adjunto), 1)
        self.assertEqual(adjunto.name, 'Estado de comisiones - Vendedor Prueba Excel - 2026-10.xlsx')
        self.assertEqual(accion, {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % adjunto.id,
            'target': 'download',
        })
        libro = openpyxl.load_workbook(io.BytesIO(base64.b64decode(adjunto.datas)))
        self.assertEqual(libro.sheetnames, HOJAS)
        celdas = [c for fila in libro['Resumen'].iter_rows(values_only=True) for c in fila]
        self.assertIn('Vendedor Prueba Excel', celdas)
        self.assertIn('octubre 2026', celdas)

    def test_no_hace_falta_consultar_antes(self):
        asistente = self._asistente()
        self.assertFalse(asistente.resumen_html)
        asistente.action_descargar_excel()
        self.assertTrue(self._adjuntos(asistente))

    def test_descargar_de_nuevo_no_acumula_archivos(self):
        asistente = self._asistente()
        asistente.action_descargar_excel()
        asistente.action_descargar_excel()
        self.assertEqual(len(self._adjuntos(asistente)), 1)

    def test_consultar_en_mes_sin_movimientos(self):
        asistente = self._asistente()
        asistente.action_consultar()
        self.assertFalse(asistente.line_ids)
        self.assertNotIn('Tramo máximo', asistente.resumen_html or '')
