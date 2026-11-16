# -*- coding: utf-8 -*-
"""Pruebas del importador único: el Importar nativo del diario reconoce el
xlsx del BAC y el CSV del Banco Nacional.

Los archivos se arman en memoria con la misma forma que los del banco.
Los tests que necesitan un diario real se saltan solos si no lo hay.
"""
import io
import re

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

try:
    import openpyxl
except ImportError:
    openpyxl = None

BN_CSV = (
    'oficina;fechaMovimiento;numeroDocumento;debito;credito;descripcion\n'
    '100;03/10/2026;90000001;0.00;25,000.00;PRUEBA IMPORTADOR UNO\n'
    '100;04/10/2026;90000002;1,500.50;0.00;PRUEBA IMPORTADOR DOS\n'
).encode('utf-8')


def xlsx_bac(iban, movimientos, saldo_inicial=1000.0):
    """xlsx con la forma del "Detalle de movimientos" del BAC.
    ``movimientos``: [(fecha dd/mm/aaaa, ref, descripcion, debito, credito)]
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['Detalle de movimientos'])
    ws.append(['Producto', iban])
    ws.append(['Fecha', 'Referencia', None, 'Código', 'Descripción', None,
               None, 'Débitos', 'Créditos', 'Balance'])
    ws.append([None, None, None, None, 'Saldo Inicial', None, None, None,
               None, saldo_inicial])
    saldo = saldo_inicial
    for fecha, ref, descripcion, debito, credito in movimientos:
        saldo += credito - debito
        ws.append([fecha, ref, None, 'TF', descripcion, None, None, debito,
                   credito, saldo])
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


@tagged('post_install', '-at_install', 'sng_importar')
class TestSngImportar(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Diario = cls.env['account.journal']
        cls.Linea = cls.env['account.bank.statement.line']

    def _diario_con_cuenta(self):
        """Diario de banco con el número de cuenta en el nombre y suspenso
        válido, en una compañía del usuario."""
        for diario in self.Diario.search(
                [('type', '=', 'bank'),
                 ('company_id', 'in', self.env.companies.ids)]):
            digitos = re.sub(r'\D', '', diario.name or '')
            suspense = diario.suspense_account_id
            if len(digitos) >= 10 and suspense \
                    and suspense.account_type != 'off_balance' \
                    and diario.default_account_id:
                return diario.with_company(diario.company_id), digitos
        return None, None

    def _adjunto(self, nombre, datos):
        return self.env['ir.attachment'].create({
            'name': nombre, 'raw': datos})

    MOVS = [
        ('05/10/2026', '77000001', 'PRUEBA IMPORTADOR A', 0, 12345.67),
        ('06/10/2026', '77000002', 'PRUEBA IMPORTADOR B', 500, 0),
        ('06/10/2026', '77000003', 'PRUEBA IMPORTADOR C', 0, 800),
    ]

    # ------------------------------------------------------------------
    # Detección por contenido
    # ------------------------------------------------------------------
    def test_detecta_formato(self):
        self.assertEqual(self.Diario._sng_detectar_formato(BN_CSV), 'bn')
        self.assertIsNone(self.Diario._sng_detectar_formato(
            b'fecha,monto\n2026-10-01,5\n'))
        if openpyxl is None:
            self.skipTest('sin openpyxl')
        self.assertEqual(self.Diario._sng_detectar_formato(
            xlsx_bac('CR00123', self.MOVS)), 'bac')
        # un xlsx cualquiera sigue el camino nativo (mapeo de columnas)
        wb = openpyxl.Workbook()
        wb.active.append(['Fecha', 'Monto'])
        salida = io.BytesIO()
        wb.save(salida)
        self.assertIsNone(
            self.Diario._sng_detectar_formato(salida.getvalue()))

    # ------------------------------------------------------------------
    # BAC por el importador nativo
    # ------------------------------------------------------------------
    def test_bac_importa_y_no_duplica(self):
        if openpyxl is None:
            self.skipTest('sin openpyxl')
        diario, digitos = self._diario_con_cuenta()
        if not diario:
            self.skipTest('sin diario de banco con cuenta en el nombre')
        datos = xlsx_bac('CR' + digitos, self.MOVS)
        diario._import_bank_statement(self._adjunto('bac.xlsx', datos))
        lineas = self.Linea.search([
            ('journal_id', '=', diario.id),
            ('payment_ref', 'like', 'PRUEBA IMPORTADOR')], order='sequence')
        self.assertEqual(lineas.mapped('amount'), [12345.67, -500.0, 800.0])
        self.assertEqual(len(lineas.statement_id), 1)
        self.assertEqual(lineas.statement_id.balance_start, 1000.0)
        self.assertTrue(all(lineas.mapped('unique_import_id')))
        # los créditos salen de la importación ya procesados
        creditos = lineas.filtered(lambda l: l.amount > 0)
        self.assertTrue(all(l.sng_sugerencia or l.sng_ia_pendiente
                            for l in creditos))
        # reimportar el mismo archivo no duplica
        with self.assertRaises(UserError):
            diario._import_bank_statement(self._adjunto('bac.xlsx', datos))
        self.assertEqual(self.Linea.search_count([
            ('journal_id', '=', diario.id),
            ('payment_ref', 'like', 'PRUEBA IMPORTADOR')]), 3)

    def test_bac_respeta_lineas_del_asistente_anterior(self):
        """Las líneas viejas tienen unique_import_id sin prefijo de
        diario: tampoco se duplican."""
        if openpyxl is None:
            self.skipTest('sin openpyxl')
        diario, digitos = self._diario_con_cuenta()
        if not diario:
            self.skipTest('sin diario de banco con cuenta en el nombre')
        self.Linea.with_context(sng_sin_barrido=True).create({
            'journal_id': diario.id, 'date': '2026-10-05',
            'payment_ref': 'TF PRUEBA IMPORTADOR A', 'amount': 12345.67,
            'unique_import_id': 'BAC-77000001-20261005-1234567'})
        diario._import_bank_statement(self._adjunto(
            'bac.xlsx', xlsx_bac('CR' + digitos, self.MOVS)))
        self.assertEqual(self.Linea.search_count([
            ('journal_id', '=', diario.id),
            ('payment_ref', 'like', 'PRUEBA IMPORTADOR')]), 3)

    def test_bac_de_otra_cuenta_se_rechaza(self):
        if openpyxl is None:
            self.skipTest('sin openpyxl')
        diario, _digitos = self._diario_con_cuenta()
        if not diario:
            self.skipTest('sin diario de banco con cuenta en el nombre')
        with self.assertRaises(UserError):
            diario._import_bank_statement(self._adjunto(
                'bac.xlsx', xlsx_bac('CR99999999999999999999', self.MOVS)))

    # ------------------------------------------------------------------
    # BN por el importador nativo
    # ------------------------------------------------------------------
    def test_bn_importa_en_el_diario_elegido(self):
        diario, _digitos = self._diario_con_cuenta()
        if not diario:
            self.skipTest('sin diario de banco con cuenta en el nombre')
        diario._import_bank_statement(self._adjunto('bn.csv', BN_CSV))
        lineas = self.Linea.search([
            ('journal_id', '=', diario.id),
            ('payment_ref', 'like', 'PRUEBA IMPORTADOR')], order='sequence')
        self.assertEqual(lineas.mapped('amount'), [25000.0, -1500.5])
