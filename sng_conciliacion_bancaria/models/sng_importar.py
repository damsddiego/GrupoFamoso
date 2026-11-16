# -*- coding: utf-8 -*-
"""Estados de cuenta del BAC y del Banco Nacional en el importador nativo.

El botón Importar del diario (Contabilidad) reconoce estos dos formatos
por el CONTENIDO del archivo y se salta el mapeo manual de columnas:

- BAC San José, "Detalle de movimientos" (xlsx): hoja con encabezado
  ("Producto" = IBAN de la cuenta, "Saldo Inicial") y tabla Fecha /
  Referencia / Código / Descripción / Débitos / Créditos / Balance.
  El IBAN del archivo debe coincidir con el diario desde el que se importa.
- Banco Nacional (csv separado por ";"): columnas oficina /
  fechaMovimiento / numeroDocumento / debito / credito / descripcion.
  El CSV NO trae número de cuenta ni saldos: vale el diario desde el que
  se importa y el extracto queda sin saldos de control.

Cualquier otro archivo sigue el camino nativo. Reimportar el mismo archivo
no duplica líneas (unique_import_id), y las líneas llegan al widget de
conciliación con la sugerencia ya calculada.
"""
import csv
import io
import logging
import re
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    openpyxl = None


def _num(valor):
    if valor in (None, ''):
        return 0.0
    return float(str(valor).replace(',', ''))


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # ------------------------------------------------------------------
    # Enganche con el importador nativo
    # ------------------------------------------------------------------
    def _get_bank_statements_available_import_formats(self):
        rslt = super()._get_bank_statements_available_import_formats()
        rslt.extend(['BAC', 'BN'])
        return rslt

    @api.model
    def _sng_detectar_formato(self, data):
        """'bac' (xlsx "Detalle de movimientos"), 'bn' (csv) o None si el
        archivo no es de estos bancos. Se decide por el CONTENIDO."""
        if data[:2] == b'PK':  # zip → xlsx
            if openpyxl is None:
                return None
            try:
                wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True,
                                            data_only=True)
                filas = wb.worksheets[0].iter_rows(max_row=60,
                                                   values_only=True)
                for fila in filas:
                    if fila and fila[0] is not None \
                            and str(fila[0]).strip() == 'Producto':
                        return 'bac'
            except Exception:  # noqa: BLE001 - no es un xlsx legible
                return None
            return None
        inicio = data[:200].decode('latin-1', 'ignore')
        if 'fechamovimiento' in inicio.replace(' ', '').lower():
            return 'bn'
        return None

    def _check_file_format(self, filename):
        # Los formatos BAC/BN no pasan por el mapeo manual de columnas
        if self.env.context.get('sng_formato_banco'):
            return False
        return super()._check_file_format(filename)

    def _import_bank_statement(self, attachments):
        if len(attachments) == 1 and attachments.raw:
            formato = self._sng_detectar_formato(attachments.raw)
            if formato:
                # sin PDF del extracto (cientos de líneas) y sin el barrido:
                # las sugerencias se calculan aquí mismo
                self = self.with_context(
                    sng_formato_banco=formato, sng_sin_barrido=True,
                    skip_pdf_attachment_generation=True)
        return super()._import_bank_statement(attachments)

    def _parse_bank_statement_file(self, attachment):
        formato = self.env.context.get('sng_formato_banco')
        if not formato:
            return super()._parse_bank_statement_file(attachment)
        if not self:
            raise UserError(_(
                'Importe el estado de cuenta desde el diario del banco '
                '(Contabilidad → tablero → Importar archivo en ese diario).'))
        self.ensure_one()
        if formato == 'bac':
            banco = 'BAC'
            iban, saldo_inicial, saldo_final, movimientos, avisos = \
                self._sng_parse_bac(attachment.raw)
            self._sng_validar_iban(iban)
        else:
            banco = 'BN'
            saldo_inicial = saldo_final = None
            movimientos, avisos = self._sng_parse_bn(attachment.raw)
        self._sng_validar_suspense()

        Linea = self.env['account.bank.statement.line']
        uids = ['%s-%s-%s-%d' % (
            banco, m['ref'] or 'SINREF', m['fecha'].strftime('%Y%m%d'),
            round((m['credito'] - m['debito']) * 100)) for m in movimientos]
        # Líneas del asistente anterior: su unique_import_id no lleva el
        # prefijo del diario que agrega el importador nativo.
        vistos = set(Linea.sudo().search(
            [('unique_import_id', 'in', uids)]).mapped('unique_import_id'))
        transacciones = []
        for idx, (m, uid) in enumerate(zip(movimientos, uids), start=1):
            monto = m['credito'] - m['debito']
            if uid in vistos or not monto:
                if saldo_inicial is not None:
                    saldo_inicial += monto
                continue
            vistos.add(uid)
            transacciones.append({
                'date': m['fecha'],
                'payment_ref': ('%s %s' % (m['codigo'],
                                           m['descripcion'])).strip(),
                'ref': m['ref'],
                'amount': monto,
                'unique_import_id': uid,
                'sequence': idx,
            })
        if not transacciones:
            raise UserError(_(
                'Este archivo ya se había importado: todas sus líneas '
                'existen en Odoo, así que no se duplicó nada.'))

        fechas = [t['date'] for t in transacciones]
        fecha_inicio = fields.Date.from_string(self.env[
            'ir.config_parameter'].sudo().get_param(
            'sng_conciliacion_bancaria.fecha_inicio') or '2026-07-01')
        if min(fechas) < fecha_inicio:
            avisos.append(_(
                'El archivo trae movimientos anteriores al %s: en esos meses '
                'los pagos se registraban directo contra la cuenta del banco '
                '(sin transitoria), así que esas líneas NO van a cruzar '
                'contra pagos registrados.') % fecha_inicio)
        if Linea._sng_suspense_choca(self):
            avisos.append(_(
                'El diario "%s" usa como cuenta de suspenso la misma '
                'transitoria de sus pagos: las sugerencias de pago se '
                'montan pero NO aparece el botón Validar. Hay que poner en '
                'el diario una cuenta de suspenso distinta.') % self.name)
        extracto = {
            'name': _('%(banco)s %(desde)s a %(hasta)s', banco=banco,
                      desde=min(fechas), hasta=max(fechas)),
            'date': max(fechas),
            'transactions': transacciones,
            'sng_avisos': avisos,
        }
        # El CSV del BN no trae saldos: el extracto queda sin control de
        # saldo inicial/final (avisado en `avisos`).
        if saldo_inicial is not None:
            extracto['balance_start'] = saldo_inicial
        if saldo_final is not None:
            extracto['balance_end_real'] = saldo_final
        return None, None, [extracto]

    def _create_bank_statements(self, stmts_vals, raise_no_imported_file=True):
        avisos = [a for st_vals in stmts_vals
                  for a in st_vals.pop('sng_avisos', [])]
        statement_ids, line_ids, notifications = super(
        )._create_bank_statements(
            stmts_vals, raise_no_imported_file=raise_no_imported_file)
        if not self.env.context.get('sng_formato_banco'):
            return statement_ids, line_ids, notifications
        # Sugerencias al tiro: así las líneas llegan al widget nativo de
        # conciliación ya montadas. Un fallo aquí nunca tumba la importación.
        try:
            procesadas, pendientes = self.env[
                'account.bank.statement.line'].browse(
                line_ids)._sng_sugerir_lote()
            avisos.insert(0, _(
                'Sugerencias: %(o)s resueltas al instante; %(q)s en cola '
                'de IA (se completan solas en unos minutos).',
                o=len(procesadas) - len(pendientes), q=len(pendientes)))
        except Exception:  # noqa: BLE001
            _logger.exception('SNG: fallo calculando sugerencias al importar '
                              'los extractos %s', statement_ids)
        notifications = notifications + [
            {'type': 'warning', 'message': ' %s' % a} for a in avisos]
        return statement_ids, line_ids, notifications

    # ------------------------------------------------------------------
    # Validaciones del diario
    # ------------------------------------------------------------------
    def _sng_validar_iban(self, iban):
        """El xlsx del BAC trae la cuenta: debe ser la de este diario (el
        nombre del diario contiene el número de cuenta)."""
        digitos_diario = re.sub(r'\D', '', self.name or '')
        if not digitos_diario \
                or digitos_diario not in re.sub(r'\D', '', iban):
            raise UserError(_(
                'El archivo es de la cuenta %(iban)s y no corresponde al '
                'diario "%(diario)s". Impórtelo desde el diario de esa '
                'cuenta (el nombre del diario debe contener el número de '
                'cuenta).', iban=iban, diario=self.name))

    def _sng_validar_suspense(self):
        suspense = self.suspense_account_id
        if not suspense or suspense.account_type == 'off_balance':
            raise UserError(_(
                'El diario "%s" no tiene una cuenta suspense válida '
                '(no puede ser de tipo fuera de balance). Corrija la '
                'configuración del diario antes de importar.') % self.name)

    # ------------------------------------------------------------------
    # Lectura de los archivos
    # ------------------------------------------------------------------
    def _sng_parse_bn(self, data):
        """CSV del Banco Nacional. Devuelve (movimientos, avisos).

        No trae número de cuenta ni saldos; los montos usan coma de miles
        y punto decimal (igual que el BAC), fechas dd/mm/aaaa.
        """
        texto = None
        for enc in ('utf-8-sig', 'latin-1'):
            try:
                texto = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if texto is None:
            raise UserError(_('No se pudo leer el CSV (codificación).'))
        movimientos = []
        for fila in csv.reader(io.StringIO(texto), delimiter=';'):
            if len(fila) < 6:
                continue
            try:
                fecha = datetime.strptime(fila[1].strip(),
                                          '%d/%m/%Y').date()
            except ValueError:
                continue  # encabezado ("fechaMovimiento") u otras filas
            try:
                debito = _num(fila[3].strip())
                credito = _num(fila[4].strip())
            except ValueError:
                continue
            movimientos.append({
                'fecha': fecha,
                'ref': fila[2].strip(),
                'codigo': '',
                'descripcion': fila[5].strip(),
                'debito': debito,
                'credito': credito,
                'balance': None,
            })
        if not movimientos:
            raise UserError(_('El archivo no trae movimientos.'))
        avisos = [_(
            'El CSV del Banco Nacional no trae número de cuenta ni saldos '
            'inicial/final: verifique que el diario elegido sea el correcto '
            'y cuadre los saldos contra el banco por aparte.')]
        return movimientos, avisos

    # ------------------------------------------------------------------
    def _sng_parse_bac(self, data):
        if openpyxl is None:
            raise UserError(_('Falta la librería Python "openpyxl".'))
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True,
                                        data_only=True)
        except Exception as exc:
            raise UserError(_('No se pudo leer el archivo como xlsx: %s')
                            % exc) from exc
        ws = wb.worksheets[0]
        iban = None
        saldo_inicial = None
        movimientos = []
        resumen = {'deb': 0.0, 'cred': 0.0, 'n': 0}
        en_tabla = False
        en_resumen = False
        for fila in ws.iter_rows(values_only=True):
            celdas = list(fila) + [None] * max(0, 12 - len(fila))
            a = str(celdas[0]).strip() if celdas[0] is not None else ''
            if a == 'Producto' and celdas[1]:
                iban = str(celdas[1]).strip()
            if a == 'Cuadro de Resumen':
                en_tabla = False
                en_resumen = True
                continue
            if en_resumen:
                # fila "Totales": cant deb / monto deb / cant cred / monto cred
                if a == 'Totales':
                    try:
                        resumen['deb'] = _num(celdas[8])
                        resumen['cred'] = _num(celdas[10])
                        resumen['n'] = int(_num(celdas[7]) + _num(celdas[9]))
                    except (ValueError, TypeError):
                        pass
                continue
            if not en_tabla:
                if (a == 'Fecha' and celdas[7]
                        and str(celdas[7]).strip() == 'Débitos'):
                    en_tabla = True
                continue
            descripcion = (str(celdas[4]).strip()
                           if celdas[4] is not None else '')
            if descripcion == 'Saldo Inicial':
                saldo_inicial = _num(celdas[9])
                continue
            try:
                fecha = datetime.strptime(a, '%d/%m/%Y').date()
            except ValueError:
                continue  # encabezados de página intercalados o pie
            movimientos.append({
                'fecha': fecha,
                'ref': str(celdas[1]).strip() if celdas[1] else '',
                'codigo': str(celdas[3]).strip() if celdas[3] else '',
                'descripcion': descripcion,
                'debito': _num(celdas[7]),
                'credito': _num(celdas[8]),
                'balance': _num(celdas[9]) if celdas[9] not in (None, '')
                           else None,
            })
        if not iban:
            raise UserError(_(
                'No se encontró la cuenta ("Producto") en el encabezado. '
                '¿Es un estado de cuenta del BAC en formato xlsx?'))
        if not movimientos:
            raise UserError(_('El archivo no trae movimientos.'))
        if saldo_inicial is None:
            raise UserError(_('No se encontró el Saldo Inicial de la tabla.'))
        saldo_final = next((m['balance'] for m in reversed(movimientos)
                            if m['balance'] is not None), None)
        # OJO: el export del BAC puede NO listar todos los movimientos
        # (planillas y pagos masivos vienen solo en el Cuadro de Resumen),
        # así que el descuadre no bloquea: se reporta como aviso.
        avisos = []
        neto = sum(m['credito'] - m['debito'] for m in movimientos)
        if saldo_final is not None and abs(
                saldo_inicial + neto - saldo_final) > 0.02:
            avisos.append(_(
                'El detalle del archivo no cuadra con sus saldos: inicial '
                '%(ini)0.2f + movimientos listados %(neto)0.2f ≠ final '
                '%(fin)0.2f. El BAC no detalla algunos movimientos en este '
                'export (típicamente planillas / pagos masivos).',
                ini=saldo_inicial, neto=neto, fin=saldo_final))
        if resumen['n'] and resumen['n'] != len(movimientos):
            faltan_deb = resumen['deb'] - sum(m['debito']
                                              for m in movimientos)
            faltan_cred = resumen['cred'] - sum(m['credito']
                                                for m in movimientos)
            avisos.append(_(
                'El archivo lista %(lis)s de %(tot)s movimientos del Cuadro '
                'de Resumen (faltan %(fd)0.2f en débitos y %(fc)0.2f en '
                'créditos, que habrá que registrar a mano).',
                lis=len(movimientos), tot=resumen['n'],
                fd=faltan_deb, fc=faltan_cred))
        return iban, saldo_inicial, saldo_final, movimientos, avisos
