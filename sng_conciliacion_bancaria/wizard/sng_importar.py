# -*- coding: utf-8 -*-
"""Importador de estados de cuenta bancarios al extracto nativo.

Formatos soportados (se detectan por el contenido del archivo):

- BAC San José, "Detalle de movimientos" (xlsx): hoja con encabezado
  ("Producto" = IBAN de la cuenta, "Saldo Inicial") y tabla Fecha /
  Referencia / Código / Descripción / Débitos / Créditos / Balance.
  El diario se detecta comparando los dígitos del IBAN con el nombre de
  los diarios de banco.
- Banco Nacional (csv separado por ";"): columnas oficina /
  fechaMovimiento / numeroDocumento / debito / credito / descripcion.
  El CSV NO trae número de cuenta ni saldos, así que el diario lo elige
  la usuaria en el asistente y el extracto queda sin saldos de control.

Reimportar el mismo archivo no duplica líneas (unique_import_id).
"""
import base64
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


class SngConciliacionImportar(models.TransientModel):
    _name = 'sng.conciliacion.importar'
    _description = 'Importar estado de cuenta bancario'

    archivo = fields.Binary(string='Estado de cuenta (BAC xlsx / BN csv)',
                            required=True)
    archivo_nombre = fields.Char(string='Nombre del archivo')
    formato = fields.Selection(
        [('bac', 'BAC (xlsx)'), ('bn', 'Banco Nacional (csv)')],
        string='Formato', readonly=True,
        help='Se deduce del archivo. Solo para el CSV del Banco Nacional '
             'hay que indicar el diario: ese archivo no trae el número de '
             'cuenta.')
    diario_id = fields.Many2one(
        'account.journal', string='Diario del banco',
        domain="[('type', '=', 'bank')]",
        help='Solo para el CSV del Banco Nacional. El xlsx del BAC trae el '
             'IBAN y el diario se detecta solo.')
    resultado = fields.Html(string='Resultado', readonly=True)
    statement_id = fields.Many2one('account.bank.statement', readonly=True)
    linea_ids = fields.Many2many('account.bank.statement.line',
                                 readonly=True)
    estado = fields.Selection([('nuevo', 'Nuevo'), ('hecho', 'Hecho')],
                              default='nuevo')

    @api.onchange('archivo_nombre')
    def _onchange_archivo_nombre(self):
        nombre = (self.archivo_nombre or '').lower()
        if nombre.endswith('.csv'):
            self.formato = 'bn'
        elif nombre.endswith(('.xlsx', '.xls')):
            self.formato = 'bac'
        else:
            self.formato = False

    # ------------------------------------------------------------------
    @api.model
    def _sng_detectar_formato(self, data):
        """'bac' (xlsx) o 'bn' (csv). Se decide por el CONTENIDO, no por el
        nombre: el nombre solo alimenta el onchange para pedir el diario."""
        if data[:2] == b'PK':  # zip → xlsx
            return 'bac'
        inicio = data[:200].decode('latin-1', 'ignore')
        if 'fechamovimiento' in inicio.replace(' ', '').lower():
            return 'bn'
        raise UserError(_(
            'Formato de archivo no reconocido. Se espera el xlsx del BAC '
            '("Detalle de movimientos") o el CSV del Banco Nacional '
            '(encabezado "oficina;fechaMovimiento;numeroDocumento;...").'))

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

    def _sng_detectar_diario(self, iban):
        digitos_iban = re.sub(r'\D', '', iban)
        candidatos = self.env['account.journal'].search(
            [('type', '=', 'bank')])
        coincidencias = candidatos.filtered(
            lambda j: re.sub(r'\D', '', j.name or '')
            and re.sub(r'\D', '', j.name) in digitos_iban)
        if len(coincidencias) > 1:
            # misma cuenta clonada en otra compañía: preferir compañías
            # activas del usuario y, de esas, la que tiene movimientos
            activas = coincidencias.filtered(
                lambda j: j.company_id in self.env.companies)
            coincidencias = activas or coincidencias
            if len(coincidencias) > 1:
                con_movs = coincidencias.filtered(
                    lambda j: self.env['account.move'].search_count(
                        [('journal_id', '=', j.id)], limit=1))
                coincidencias = con_movs or coincidencias
        if len(coincidencias) != 1:
            raise UserError(_(
                'No se pudo identificar el diario para la cuenta %(iban)s '
                '(coincidencias: %(n)s). El nombre del diario debe contener '
                'el número de cuenta.', iban=iban, n=len(coincidencias)))
        diario = coincidencias
        self._sng_validar_suspense(diario)
        return diario

    @api.model
    def _sng_validar_suspense(self, diario):
        suspense = diario.suspense_account_id
        if not suspense or suspense.account_type == 'off_balance':
            raise UserError(_(
                'El diario "%s" no tiene una cuenta suspense válida '
                '(no puede ser de tipo fuera de balance). Corrija la '
                'configuración del diario antes de importar.') % diario.name)

    # ------------------------------------------------------------------
    def accion_importar(self):
        self.ensure_one()
        if not self.env.user.has_group(
                'sng_conciliacion_bancaria.group_sng_conciliacion'):
            raise UserError(_(
                'Necesita el permiso "Conciliación bancaria (IA)".'))
        data = base64.b64decode(self.archivo)
        formato = self._sng_detectar_formato(data)
        if formato == 'bac':
            banco = 'BAC'
            iban, saldo_inicial, saldo_final, movimientos, avisos = \
                self._sng_parse_bac(data)
            diario = self._sng_detectar_diario(iban)
        else:
            banco = 'BN'
            saldo_inicial = saldo_final = None
            movimientos, avisos = self._sng_parse_bn(data)
            diario = self.diario_id
            if not diario:
                raise UserError(_(
                    'El CSV del Banco Nacional no trae el número de cuenta: '
                    'seleccione el diario del banco en el asistente.'))
            self._sng_validar_suspense(diario)

        # dedup contra líneas ya importadas
        def uid(m):
            return '%s-%s-%s-%d' % (
                banco, m['ref'] or 'SINREF', m['fecha'].strftime('%Y%m%d'),
                round((m['credito'] - m['debito']) * 100))
        uids = [uid(m) for m in movimientos]
        lineas_previas = self.env['account.bank.statement.line'].search(
            [('unique_import_id', 'in', uids)])
        existentes = set(lineas_previas.mapped('unique_import_id'))
        nuevos, saltados = [], 0
        vistos = set(existentes)
        for m in movimientos:
            u = uid(m)
            if u in vistos:
                saltados += 1
                continue
            vistos.add(u)
            monto = m['credito'] - m['debito']
            if not monto:
                saltados += 1
                continue
            nuevos.append((m, u, monto))
        if not nuevos:
            sin_conciliar = len(lineas_previas.filtered(
                lambda l: not l.is_reconciled))
            self.write({
                'estado': 'hecho',
                'linea_ids': [(6, 0, lineas_previas.ids)],
                'resultado': (
                    '<p><b>%s</b></p><p>%s</p><p>%s</p>' % (
                        _('Este archivo ya se había importado'),
                        _('Las %(t)s líneas del archivo ya existen en Odoo, '
                          'así que no se duplicó nada. De ellas, %(p)s '
                          'siguen pendientes de conciliar.',
                          t=len(lineas_previas), p=sin_conciliar),
                        _('Pulse "Ver líneas importadas" para verlas. '
                          'También las encuentra en el menú Conciliación IA '
                          '→ Líneas del extracto (ojo: esa vista filtra '
                          '"Sin conciliar" por defecto; si ya las concilió, '
                          'quite el filtro para verlas).'),
                    )),
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        fechas = [m['fecha'] for m, _u, _mto in nuevos]
        statement_vals = {
            'name': _('%(banco)s %(desde)s a %(hasta)s', banco=banco,
                      desde=min(fechas), hasta=max(fechas)),
            'date': max(fechas),
        }
        # El CSV del BN no trae saldos: el extracto queda sin control de
        # saldo inicial/final (avisado en `avisos`).
        if saldo_inicial is not None:
            statement_vals['balance_start'] = saldo_inicial
        if saldo_final is not None:
            statement_vals['balance_end_real'] = saldo_final
        statement = self.env['account.bank.statement'].create(statement_vals)
        # Las líneas se crean aparte del statement (no anidadas) en lote.
        lineas_nuevas = self.env['account.bank.statement.line'].create([{
            'statement_id': statement.id,
            'journal_id': diario.id,
            'date': m['fecha'],
            'payment_ref': ('%s %s' % (m['codigo'],
                                       m['descripcion'])).strip(),
            'ref': m['ref'],
            'amount': monto,
            'unique_import_id': u,
            'sequence': idx,
        } for idx, (m, u, monto) in enumerate(nuevos, start=1)])

        fecha_inicio = fields.Date.from_string(
            self.env['ir.config_parameter'].sudo().get_param(
                'sng_conciliacion_bancaria.fecha_inicio') or '2026-07-01')
        if min(fechas) < fecha_inicio:
            avisos.append(_(
                'El archivo trae movimientos anteriores al %s: en esos meses '
                'los pagos se registraban directo contra la cuenta del banco '
                '(sin transitoria), así que esas líneas NO van a cruzar '
                'contra pagos registrados.') % fecha_inicio)
        creditos = sum(1 for m, _u, mto in nuevos if mto > 0)
        self.write({
            'estado': 'hecho',
            'statement_id': statement.id,
            'linea_ids': [(6, 0, lineas_nuevas.ids)],
            'resultado': (
                '<p><b>%s</b></p><ul><li>%s</li><li>%s</li>%s</ul>'
                '<p class="mt-3"><b>%s</b></p><ol>'
                '<li>%s</li><li>%s</li><li>%s</li><li>%s</li></ol>' % (
                    _('Importación completada — diario %s') % diario.name,
                    _('%(n)s líneas nuevas (%(c)s créditos, %(d)s débitos); '
                      '%(s)s saltadas (duplicadas o en cero)',
                      n=len(nuevos), c=creditos, d=len(nuevos) - creditos,
                      s=saltados),
                    _('Saldos del archivo: inicial %(i).2f → final %(f).2f',
                      i=saldo_inicial, f=saldo_final or 0)
                    if saldo_inicial is not None
                    else _('El archivo no trae saldos de control (CSV BN).'),
                    ''.join('<li class="text-warning">%s</li>' % a
                            for a in avisos),
                    _('Siguiente paso — cómo conciliar:'),
                    _('Pulse "Ver líneas importadas".'),
                    _('Seleccione las líneas y pulse "1 · Sugerir con IA": '
                      'solo llena la columna Sugerencia, todavía no concilia '
                      'nada. Las líneas ambiguas quedan en cola de IA y se '
                      'completan solas en unos minutos (columna "IA en '
                      'cola"; refresque la vista).'),
                    _('Revise las columnas Sugerencia, Confianza y Motivo.'),
                    _('En las líneas que esté de acuerdo, pulse '
                      '"2 · Conciliar lo sugerido". Es reversible desde el '
                      'extracto bancario.'),
                )),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def accion_ver_lineas(self):
        self.ensure_one()
        if self.linea_ids:
            domain = [('id', 'in', self.linea_ids.ids)]
        else:
            domain = [('statement_id', '=', self.statement_id.id)]
        # Sin filtro "Sin conciliar": aquí la usuaria quiere ver TODO lo
        # que trae el archivo, conciliado o no.
        return {
            'type': 'ir.actions.act_window',
            'name': _('Líneas del extracto'),
            'res_model': 'account.bank.statement.line',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('sng_conciliacion_bancaria.'
                              'view_sng_statement_line_list').id, 'list'),
                (self.env.ref('sng_conciliacion_bancaria.'
                              'view_sng_statement_line_form').id, 'form'),
            ],
            'search_view_id': self.env.ref(
                'sng_conciliacion_bancaria.view_sng_statement_line_search'
            ).id,
            'domain': domain,
        }
