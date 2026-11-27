# -*- coding: utf-8 -*-
"""Libro de Excel del reporte Sell in / Sell out.

Lógica pura (sin Odoo): recibe el dict que arma el asistente
``sng.comercial.sell.wizard`` y devuelve el archivo .xlsx con cuatro hojas:
BASE DATOS (una fila por producto), POR MES (producto y mes), TABLA (litros
por pilar y base) y Notas.

``datos``::

    {
        'companias': 'SAASA',                 # texto para los títulos
        'periodo': '01/07/2026 al 30/11/2026',
        'corte': 'Datos de Odoo al ...',
        'meses': ['2026-07', '2026-08'],      # columnas de mes, en orden
        'filas': [{
            'compania', 'codigo', 'descripcion', 'base', 'pilar',
            'volumen',                        # litros por unidad
            'stock', 'transito', 'bodega',
            'in_mes': {'2026-07': 10.0}, 'out_mes': {...},
            'proveedores',
        }],
    }
"""
import io
from collections import defaultdict

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')

# Paleta de sngcloud.app
AZUL = '#016E94'
TURQUESA = '#1BAAA0'
AZUL_OSCURO = '#045FA0'
GRIS = '#32373C'
GRIS_SUAVE = '#6B7280'
AZUL_PALIDO = '#E6F1F5'
TURQUESA_PALIDO = '#E8F6F5'
BORDE = '#D5DDE2'
FUENTE = 'Calibri'

HEAD = 3            # fila de encabezados (índice 0)
FIRST = HEAD + 1    # primera fila de datos


def nombre_mes(mes):
    """«Julio 2026» a partir de «2026-07»."""
    anio, numero = mes.split('-')
    return '%s %s' % (MESES[int(numero) - 1].capitalize(), anio)


def _total_mes(fila, clave):
    return sum(fila[clave].values())


def generar(datos):
    salida = io.BytesIO()
    workbook = xlsxwriter.Workbook(salida, {'in_memory': True})
    workbook.set_properties({
        'title': 'Sell in / Sell out - %s' % datos['periodo'],
        'subject': 'Compras recibidas y ventas facturadas en unidades y litros',
        'author': 'SNG CLOUD',
        'company': 'SNG CLOUD',
    })
    workbook.formats[0].set_font_name(FUENTE)
    workbook.formats[0].set_font_size(10)

    def fmt(**props):
        props.setdefault('font_name', FUENTE)
        props.setdefault('font_size', 10)
        props.setdefault('font_color', GRIS)
        return workbook.add_format(props)

    celda = {'border': 1, 'border_color': BORDE, 'valign': 'vcenter'}
    numero = '#,##0.##;[Red]-#,##0.##'
    f = {
        'title': fmt(bold=True, font_size=16, font_color='#FFFFFF', bg_color=AZUL, valign='vcenter', indent=1),
        'corte': fmt(font_size=9, font_color=GRIS_SUAVE, valign='vcenter', indent=1),
        'header': fmt(bold=True, font_color='#FFFFFF', bg_color=AZUL, align='center', text_wrap=True, **celda),
        'header_in': fmt(bold=True, font_color='#FFFFFF', bg_color=TURQUESA, align='center', text_wrap=True, **celda),
        'header_out': fmt(bold=True, font_color='#FFFFFF', bg_color=AZUL_OSCURO, align='center', text_wrap=True, **celda),
        'text': fmt(**celda),
        'text_bold': fmt(bold=True, **celda),
        'num': fmt(num_format=numero, **celda),
        'in': fmt(num_format=numero, bg_color=TURQUESA_PALIDO, **celda),
        'out': fmt(num_format=numero, bg_color=AZUL_PALIDO, **celda),
        'total_label': fmt(bold=True, font_color='#FFFFFF', bg_color=AZUL_OSCURO, **celda),
        'total_num': fmt(bold=True, font_color='#FFFFFF', bg_color=AZUL_OSCURO,
                         num_format='#,##0.##;-#,##0.##', **celda),
        'note': fmt(text_wrap=True, valign='top'),
        'note_title': fmt(bold=True, font_color=AZUL, valign='top'),
    }

    # Se crean en el orden en que se leen.
    hojas = {nombre: workbook.add_worksheet(nombre) for nombre in ('BASE DATOS', 'POR MES', 'TABLA', 'Notas')}
    _hoja_base(hojas['BASE DATOS'], datos, f)
    _hoja_por_mes(hojas['POR MES'], datos, f)
    _hoja_tabla(hojas['TABLA'], datos, f)
    _hoja_notas(hojas['Notas'], datos, f)

    workbook.close()
    return salida.getvalue()


def _encabezado(ws, ultima_col, titulo, subtitulo, f):
    ws.set_row(0, 34)
    ws.merge_range(0, 0, 0, ultima_col, titulo, f['title'])
    ws.merge_range(1, 0, 1, ultima_col, subtitulo, f['corte'])


def _fila_total(ws, fila, ultima_col, sumas, f):
    """Fila de totales: ``sumas`` es {columna: valor}; se escribe como SUBTOTAL
    para que respete los filtros."""
    ws.write(fila, 0, 'Total', f['total_label'])
    for col in range(1, ultima_col + 1):
        if col in sumas:
            letra = xl_col_to_name(col)
            ws.write_formula(fila, col, '=SUBTOTAL(109,%s%d:%s%d)' % (letra, FIRST + 1, letra, fila),
                             f['total_num'], sumas[col])
        else:
            ws.write_blank(fila, col, None, f['total_label'])


def _hoja_base(ws, datos, f):
    filas = datos['filas']
    # (título, ancho, clave o fórmula, formato de encabezado, formato de celda)
    columnas = [
        ('CÓDIGO', 10, 'codigo', 'header', 'text'),
        ('BASE', 15, 'base', 'header', 'text'),
        ('PILAR', 9, 'pilar', 'header', 'text'),
        ('DESCRIPCIÓN', 58, 'descripcion', 'header', 'text'),
        ('VOLUMEN (L)', 9, 'volumen', 'header', 'num'),
        ('STOCK', 10, 'stock', 'header', 'num'),
        ('TRÁNSITO', 10, 'transito', 'header', 'num'),
        ('BODEGA GRUPO', 10, 'bodega', 'header', 'num'),
        ('TOTAL', 10, '=F{r}+G{r}+H{r}', 'header', 'num'),
        ('TOTAL LITROS', 12, '=I{r}*E{r}', 'header', 'num'),
        ('SELL IN UNIDADES', 11, 'sell_in', 'header_in', 'in'),
        ('SELL IN LITROS', 12, '=K{r}*E{r}', 'header_in', 'in'),
        ('SELL OUT UNIDADES', 11, 'sell_out', 'header_out', 'out'),
        ('SELL OUT LITROS', 12, '=M{r}*E{r}', 'header_out', 'out'),
        ('PROVEEDOR', 40, 'proveedores', 'header', 'text'),
        ('COMPAÑÍA', 30, 'compania', 'header', 'text'),
    ]
    ultima = len(columnas) - 1
    _encabezado(ws, ultima, 'Sell in / Sell out · %s · %s' % (datos['companias'], datos['periodo']),
                datos['corte'], f)
    ws.set_row(HEAD, 32)
    for col, (titulo, ancho, _clave, estilo, _celda) in enumerate(columnas):
        ws.set_column(col, col, ancho)
        ws.write(HEAD, col, titulo, f[estilo])

    sumas = defaultdict(float)
    for offset, fila in enumerate(filas):
        r = FIRST + offset
        total = fila['stock'] + fila['transito'] + fila['bodega']
        valores = dict(fila, sell_in=_total_mes(fila, 'in_mes'), sell_out=_total_mes(fila, 'out_mes'))
        calculados = {
            8: total,
            9: total * fila['volumen'],
            11: valores['sell_in'] * fila['volumen'],
            13: valores['sell_out'] * fila['volumen'],
        }
        for col, (_titulo, _ancho, clave, _estilo, celda) in enumerate(columnas):
            if clave.startswith('='):
                valor = calculados[col]
                ws.write_formula(r, col, clave.format(r=r + 1), f[celda], valor)
            else:
                valor = valores[clave]
                if isinstance(valor, str):
                    ws.write_string(r, col, valor, f[celda])
                    continue
                ws.write_number(r, col, valor, f[celda])
            if 5 <= col <= 13:
                sumas[col] += valor
    last = FIRST + len(filas) - 1
    _fila_total(ws, last + 1, ultima, {col: sumas[col] for col in range(5, 14)}, f)
    ws.autofilter(HEAD, 0, last, ultima)
    ws.freeze_panes(FIRST, 1)


def _hoja_por_mes(ws, datos, f):
    columnas = [
        ('MES', 16), ('CÓDIGO', 10), ('DESCRIPCIÓN', 58), ('BASE', 15), ('PILAR', 9), ('VOLUMEN (L)', 9),
        ('SELL IN UNIDADES', 11), ('SELL IN LITROS', 12), ('SELL OUT UNIDADES', 11), ('SELL OUT LITROS', 12),
        ('COMPAÑÍA', 30),
    ]
    ultima = len(columnas) - 1
    _encabezado(ws, ultima, 'Sell in / Sell out por mes · %s · %s' % (datos['companias'], datos['periodo']),
                'Una fila por producto y mes. Úsala para tablas dinámicas o filtros.', f)
    ws.set_row(HEAD, 32)
    for col, (titulo, ancho) in enumerate(columnas):
        ws.set_column(col, col, ancho)
        estilo = 'header_in' if col in (6, 7) else 'header_out' if col in (8, 9) else 'header'
        ws.write(HEAD, col, titulo, f[estilo])

    sumas = defaultdict(float)
    r = FIRST
    for mes in datos['meses']:
        for fila in datos['filas']:
            qty_in, qty_out = fila['in_mes'].get(mes, 0.0), fila['out_mes'].get(mes, 0.0)
            ws.write_string(r, 0, nombre_mes(mes), f['text'])
            ws.write_string(r, 1, fila['codigo'], f['text'])
            ws.write_string(r, 2, fila['descripcion'], f['text'])
            ws.write_string(r, 3, fila['base'], f['text'])
            ws.write_string(r, 4, fila['pilar'], f['text'])
            ws.write_number(r, 5, fila['volumen'], f['num'])
            ws.write_number(r, 6, qty_in, f['in'])
            ws.write_formula(r, 7, '=G%d*F%d' % (r + 1, r + 1), f['in'], qty_in * fila['volumen'])
            ws.write_number(r, 8, qty_out, f['out'])
            ws.write_formula(r, 9, '=I%d*F%d' % (r + 1, r + 1), f['out'], qty_out * fila['volumen'])
            ws.write_string(r, 10, fila['compania'], f['text'])
            sumas[6] += qty_in
            sumas[7] += qty_in * fila['volumen']
            sumas[8] += qty_out
            sumas[9] += qty_out * fila['volumen']
            r += 1
    _fila_total(ws, r, ultima, {col: sumas[col] for col in range(6, 10)}, f)
    ws.autofilter(HEAD, 0, r - 1, ultima)
    ws.freeze_panes(FIRST, 2)


def _hoja_tabla(ws, datos, f):
    """Litros por PILAR → BASE: inventario, sell in y sell out por mes y total."""
    meses = datos['meses']
    grupos = defaultdict(list)
    for fila in datos['filas']:
        grupos[(fila['pilar'], fila['base'] or '(sin base)')].append(fila)
    claves = sorted(grupos)

    titulos = ['PILAR', 'BASE', 'LITROS INVENTARIO']
    titulos += ['SELL IN L %s' % nombre_mes(mes) for mes in meses] + ['SELL IN L TOTAL']
    titulos += ['SELL OUT L %s' % nombre_mes(mes) for mes in meses] + ['SELL OUT L TOTAL']
    ultima = len(titulos) - 1
    _encabezado(ws, ultima, 'Litros por pilar y base · %s · %s' % (datos['companias'], datos['periodo']),
                'Inventario = stock + tránsito + bodega grupo, en litros. Sell in y sell out en litros por mes.', f)
    ws.set_row(HEAD, 42)
    ws.set_column(0, 1, 15)
    ws.set_column(2, ultima, 12)
    inicio_out = 3 + len(meses) + 1
    for col, titulo in enumerate(titulos):
        estilo = 'header' if col < 3 else 'header_in' if col < inicio_out else 'header_out'
        ws.write(HEAD, col, titulo, f[estilo])

    sumas = defaultdict(float)
    r = FIRST
    pilar_previo = None
    for pilar, base in claves:
        filas = grupos[(pilar, base)]
        ws.write_string(r, 0, pilar if pilar != pilar_previo else '', f['text_bold'])
        pilar_previo = pilar
        ws.write_string(r, 1, base, f['text'])
        inventario = sum((x['stock'] + x['transito'] + x['bodega']) * x['volumen'] for x in filas)
        ws.write_number(r, 2, inventario, f['num'])
        sumas[2] += inventario
        col = 3
        for clave, celda in (('in_mes', 'in'), ('out_mes', 'out')):
            total = 0.0
            for mes in meses:
                litros = sum(x[clave].get(mes, 0.0) * x['volumen'] for x in filas)
                ws.write_number(r, col, litros, f[celda])
                sumas[col] += litros
                total += litros
                col += 1
            if meses:
                rango = '%s%d:%s%d' % (xl_col_to_name(col - len(meses)), r + 1, xl_col_to_name(col - 1), r + 1)
                ws.write_formula(r, col, '=SUM(%s)' % rango, f[celda], total)
            else:
                ws.write_number(r, col, 0, f[celda])
            sumas[col] += total
            col += 1
        r += 1
    ws.write(r, 0, 'Total', f['total_label'])
    ws.write_blank(r, 1, None, f['total_label'])
    for col in range(2, ultima + 1):
        letra = xl_col_to_name(col)
        ws.write_formula(r, col, '=SUM(%s%d:%s%d)' % (letra, FIRST + 1, letra, r), f['total_num'], sumas[col])
    ws.freeze_panes(FIRST, 2)


def _hoja_notas(ws, datos, f):
    ws.hide_gridlines(2)
    ws.set_column(0, 0, 24)
    ws.set_column(1, 1, 100)
    _encabezado(ws, 1, 'Cómo leer este reporte', datos['corte'], f)
    notas = [
        ('Productos', 'Productos con valor en el atributo de pilar, de las compañías: %s.' % datos['companias']),
        ('Periodo', 'Del %s. %s' % (datos['periodo'], datos['corte'])),
        ('Sell in', 'Compras recibidas: cantidades que entraron a bodega desde órdenes de compra, menos '
                    'devoluciones a proveedor. Mes = fecha de recepción (hora de Costa Rica).'),
        ('Sell out', 'Cantidades facturadas desde órdenes de venta: facturas de cliente publicadas menos notas '
                     'de crédito publicadas, solo líneas ligadas a una orden de venta. Mes = fecha de la factura.'),
        ('Litros', 'Cantidad × VOLUMEN (litros por unidad del valor del atributo de volumen: '
                   '1L = 1, 400 ml = 0.4, estañón = 208).'),
        ('Inventario', 'STOCK es el inventario actual en ubicaciones internas de la compañía. TRÁNSITO es lo '
                       'pendiente de recibir en órdenes de compra confirmadas. BODEGA GRUPO es el stock de la '
                       'compañía bodega del grupo para la misma referencia interna. Son datos al momento de '
                       'generar el archivo, no del periodo.'),
    ]
    for offset, (titulo, texto) in enumerate(notas):
        ws.set_row(HEAD + offset, 45)
        ws.write(HEAD + offset, 0, titulo, f['note_title'])
        ws.write(HEAD + offset, 1, texto, f['note'])
