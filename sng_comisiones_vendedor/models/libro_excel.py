# -*- coding: utf-8 -*-
"""Libro de Excel del estado de comisiones.

Lógica pura (sin Odoo): recibe el dict de ``cruces.armar_estado`` (lo mismo
que ve el vendedor en la app y la oficina en el asistente) y devuelve el
archivo .xlsx: una hoja de resumen y una hoja por cruce.
"""
import datetime
import io

import xlsxwriter

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
SITUACION = {
    'verificado': 'Verificado',
    'sin_verificar': 'Sin verificar',
    'no_aplicado': 'No aplicado',
    'anulado': 'Anulado',
    'rechazado': 'Rechazado',
}
CLASE_ANULADO = {
    'rehecho': 'Rehecho',
    'duplicado': 'Duplicado',
    'feria': 'Feria',
    'sin_reemplazo': 'Sin reemplazo',
}
# (hoja, clave del cruce, columnas propias de la hoja después de «Monto»)
HOJAS = (
    ('Reportados', 'reportados', ('Base comisión', 'Estado', 'Situación')),
    ('Anulados', 'anulados', ('Estado', 'Clase', 'Detalle', 'Anuló', 'Anulado el',
                              'Pago que lo reemplaza', 'Monto del reemplazo', 'Diferencia')),
    ('Registrados por otro', 'registrados_por_otro', ('Base comisión', 'Estado')),
    ('Comisión de otro', 'comision_de_otro', ('Estado', 'Comisión de')),
    ('Sin comisión', 'sin_comision', ('Base en proceso', 'Estado', 'Motivo')),
    ('Reversos', 'reversos', ('Estado', 'Motivo', 'Mes original', 'Ajuste')),
)
COMUNES = ('Pago', 'Recibo', 'Fecha', 'Confirmado', 'Cliente', 'Compañía', 'Monto')
FINALES = ('Registrado por', 'Facturas')
MONTOS = {'Monto', 'Base comisión', 'Base en proceso', 'Monto del reemplazo', 'Diferencia', 'Ajuste'}
SUMAN = {'Monto', 'Base comisión', 'Base en proceso', 'Ajuste'}
FECHAS = {'Fecha', 'Confirmado', 'Anulado el'}
ANCHOS = {'Pago': 20, 'Recibo': 10, 'Cliente': 38, 'Compañía': 30, 'Detalle': 34, 'Motivo': 44,
          'Pago que lo reemplaza': 22, 'Monto del reemplazo': 20, 'Registrado por': 30, 'Facturas': 34,
          'Comisión de': 34, 'Mes original': 16, 'Anuló': 24}


def colones(monto):
    return '₡{:,.2f}'.format(monto or 0.0)


def mes_texto(iso):
    """«octubre 2026» a partir de AAAA-MM-DD."""
    fecha = _fecha(iso)
    return '%s %s' % (MESES[fecha.month - 1], fecha.year) if fecha else (iso or '')


def siguiente_tramo_texto(fila):
    """Cuánto falta para el siguiente tramo. Solo tiene sentido en un mes
    abierto: en uno cerrado el tramo ya no cambia."""
    if fila.get('estado') != 'draft':
        return ''
    siguiente = fila.get('siguiente_tramo')
    if not siguiente:
        return 'Tramo máximo'
    return 'Faltan %s para %g %%' % (colones(siguiente['falta']), siguiente['porcentaje'])


def _fecha(iso):
    """Fecha de un texto ISO (con o sin hora); None si viene vacío."""
    try:
        return datetime.date.fromisoformat((iso or '')[:10])
    except ValueError:
        return None


def _valor(columna, pago):
    reemplazo = pago.get('reemplazo') or {}
    if columna == 'Pago':
        # En borrador, o anulado sin asiento, el pago no tiene número.
        return pago.get('nombre') or 'Sin número (id %s)' % pago.get('id')
    if columna == 'Recibo':
        return pago.get('recibo')
    if columna == 'Fecha':
        return _fecha(pago.get('fecha'))
    if columna == 'Confirmado':
        return _fecha(pago.get('fecha_confirmacion'))
    if columna == 'Cliente':
        return pago.get('cliente')
    if columna == 'Compañía':
        return pago.get('compania')
    if columna == 'Monto':
        return pago.get('monto') or 0.0
    if columna in ('Base comisión', 'Base en proceso'):
        return pago.get('base') or 0.0
    if columna == 'Estado':
        return pago.get('estado_texto')
    if columna == 'Situación':
        return SITUACION.get(pago.get('clase'), pago.get('clase'))
    if columna == 'Clase':
        return CLASE_ANULADO.get(pago.get('clase'), pago.get('clase'))
    if columna == 'Detalle':
        return pago.get('detalle')
    if columna == 'Anuló':
        return pago.get('anulado_por')
    if columna == 'Anulado el':
        return _fecha(pago.get('anulado_el'))
    if columna == 'Pago que lo reemplaza':
        return _valor('Pago', reemplazo) if reemplazo else None
    if columna == 'Monto del reemplazo':
        return reemplazo.get('monto') if reemplazo else None
    if columna == 'Diferencia':
        return round(reemplazo.get('monto', 0.0) - (pago.get('monto') or 0.0), 2) if reemplazo else None
    if columna == 'Comisión de':
        return pago.get('comision_a')
    if columna == 'Motivo':
        return pago.get('motivo')
    if columna == 'Mes original':
        return mes_texto(pago.get('periodo_original'))
    if columna == 'Ajuste':
        return pago.get('ajuste') or 0.0
    if columna == 'Registrado por':
        return (pago.get('registrado_por') or {}).get('nombre')
    if columna == 'Facturas':
        return ', '.join(pago.get('facturas') or [])
    return None


def generar(estado):
    """Contenido (bytes) del .xlsx del estado de comisiones."""
    salida = io.BytesIO()
    libro = xlsxwriter.Workbook(salida, {'in_memory': True})
    f = {
        'titulo': libro.add_format({'bold': True, 'font_size': 14, 'font_color': '#016E94'}),
        'seccion': libro.add_format({'bold': True, 'font_size': 11, 'font_color': '#016E94'}),
        'etiqueta': libro.add_format({'bold': True}),
        'encabezado': libro.add_format({'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#016E94',
                                        'border': 1, 'text_wrap': True, 'valign': 'vcenter'}),
        'monto': libro.add_format({'num_format': '#,##0.00'}),
        'fecha': libro.add_format({'num_format': 'dd/mm/yyyy', 'align': 'left'}),
        'total': libro.add_format({'bold': True, 'top': 1}),
        'total_monto': libro.add_format({'bold': True, 'top': 1, 'num_format': '#,##0.00'}),
    }
    _hoja_resumen(libro.add_worksheet('Resumen'), estado, f)
    for nombre, clave, propias in HOJAS:
        _hoja_cruce(libro.add_worksheet(nombre), estado['cruces'][clave], COMUNES + propias + FINALES, f)
    libro.close()
    return salida.getvalue()


def _hoja_resumen(hoja, estado, f):
    hoja.set_column(0, 0, 34)
    hoja.set_column(1, 1, 30)
    hoja.set_column(2, 11, 20)
    generado = estado.get('generado') or ''
    try:
        generado = datetime.datetime.fromisoformat(generado).strftime('%d/%m/%Y %H:%M')
    except ValueError:
        pass
    hoja.write(0, 0, 'Estado de comisiones', f['titulo'])
    for fila, (etiqueta, valor) in enumerate((
            ('Vendedor', estado['vendedor']['nombre']),
            ('Mes', mes_texto(estado['periodo'])),
            ('Generado', generado)), start=1):
        hoja.write(fila, 0, etiqueta, f['etiqueta'])
        hoja.write(fila, 1, valor)

    fila = 5
    # Una fila por comisión: el cuadro junta lo cobrado en todas sus compañías.
    encabezados = ('Cuadro', 'Vendedor', 'Estado', 'Base', 'Tramo %', 'Comisión', 'Ajustes', 'En proceso',
                   'Siguiente tramo', 'Base proyectada', 'Tramo proyectado %', 'Comisión proyectada')
    for col, texto in enumerate(encabezados):
        hoja.write(fila, col, texto, f['encabezado'])
    for r in estado['resumen']:
        fila += 1
        proyeccion = r.get('proyeccion') or {}
        hoja.write(fila, 0, r['cuadro'])
        hoja.write(fila, 1, r.get('vendedor') or '')
        hoja.write(fila, 2, r['estado_texto'] + (' (estimado)' if r['estimado'] else ''))
        hoja.write_number(fila, 3, r['base'], f['monto'])
        hoja.write_number(fila, 4, r['porcentaje'])
        hoja.write_number(fila, 5, r['comision'], f['monto'])
        hoja.write_number(fila, 6, r['ajustes'], f['monto'])
        hoja.write_number(fila, 7, r['en_proceso'], f['monto'])
        hoja.write(fila, 8, siguiente_tramo_texto(r))
        if proyeccion:
            hoja.write_number(fila, 9, proyeccion['base'], f['monto'])
            hoja.write_number(fila, 10, proyeccion['porcentaje'])
            hoja.write_number(fila, 11, proyeccion['comision'], f['monto'])
    fila += 1
    hoja.write(fila, 0, 'Total', f['total'])
    for col in (1, 2, 4, 6, 8, 9, 10, 11):
        hoja.write_blank(fila, col, None, f['total'])
    hoja.write_number(fila, 3, estado['totales']['base'], f['total_monto'])
    hoja.write_number(fila, 5, estado['totales']['comision'], f['total_monto'])
    hoja.write_number(fila, 7, estado['totales']['en_proceso'], f['total_monto'])

    if any(r.get('companias') for r in estado['resumen']):
        fila += 2
        hoja.write(fila, 0, 'Por compañía', f['seccion'])
        fila += 1
        for col, texto in enumerate(('Cuadro', 'Compañía', 'Cobrado', 'Base', 'Comisión', 'Ajustes')):
            hoja.write(fila, col, texto, f['encabezado'])
        for r in estado['resumen']:
            for c in r.get('companias') or []:
                fila += 1
                hoja.write(fila, 0, r['cuadro'])
                hoja.write(fila, 1, c['compania'])
                for col, clave in enumerate(('cobrado', 'base', 'comision', 'ajustes'), start=2):
                    hoja.write_number(fila, col, c[clave], f['monto'])

    cruces = estado['cruces']
    estados = cruces['reportados']['por_estado']
    anulados = cruces['anulados']
    detalles = {
        'reportados': 'Verificados %s, sin verificar %s, no aplicados %s, anulados %s, rechazados %s' % (
            estados['verificado'], estados['sin_verificar'], estados['no_aplicado'],
            estados['anulado'], estados['rechazado']),
        'anulados': 'Rehechos %s, duplicados %s, feria %s, sin reemplazo %s' % (
            anulados['rehechos'], anulados['duplicados'], anulados['feria'], anulados['sin_reemplazo']),
        'registrados_por_otro': 'Base de comisión %s' % colones(cruces['registrados_por_otro']['base']),
        'reversos': 'Ajuste %s' % colones(cruces['reversos']['ajuste']),
    }
    fila += 2
    for col, texto in enumerate(('Cruce', 'Cantidad', 'Monto', 'Detalle')):
        hoja.write(fila, col, texto, f['encabezado'])
    for nombre, clave, _propias in HOJAS:
        fila += 1
        hoja.write(fila, 0, nombre)
        hoja.write_number(fila, 1, cruces[clave]['cantidad'])
        hoja.write_number(fila, 2, cruces[clave]['monto'], f['monto'])
        hoja.write(fila, 3, detalles.get(clave, ''))

    por_quien = cruces['registrados_por_otro'].get('por_quien') or []
    if por_quien:
        fila += 2
        hoja.write(fila, 0, 'Registrados por otro, por quién', f['seccion'])
        fila += 1
        for col, texto in enumerate(('Quién', 'Cantidad', 'Base comisión')):
            hoja.write(fila, col, texto, f['encabezado'])
        for quien in por_quien:
            fila += 1
            hoja.write(fila, 0, quien['nombre'])
            hoja.write_number(fila, 1, quien['cantidad'])
            hoja.write_number(fila, 2, quien['base'], f['monto'])


def _hoja_cruce(hoja, grupo, columnas, f):
    for col, columna in enumerate(columnas):
        hoja.write(0, col, columna, f['encabezado'])
        hoja.set_column(col, col, ANCHOS.get(columna, 16))
    pagos = grupo['pagos']
    for fila, pago in enumerate(pagos, start=1):
        for col, columna in enumerate(columnas):
            valor = _valor(columna, pago)
            if valor is None or valor == '':
                continue
            if columna in FECHAS:
                hoja.write_datetime(fila, col, valor, f['fecha'])
            elif columna in MONTOS:
                hoja.write_number(fila, col, valor, f['monto'])
            else:
                hoja.write(fila, col, valor)
    fila = len(pagos) + 1
    for col, columna in enumerate(columnas):
        if col == 0:
            hoja.write(fila, col, 'Total', f['total'])
        elif columna == 'Monto':
            # El mismo total que muestra el asistente, no una suma aparte.
            hoja.write_number(fila, col, grupo['monto'], f['total_monto'])
        elif columna in SUMAN:
            hoja.write_number(fila, col, round(sum(_valor(columna, p) or 0.0 for p in pagos), 2), f['total_monto'])
        else:
            hoja.write_blank(fila, col, None, f['total'])
    hoja.freeze_panes(1, 0)
    if pagos:
        hoja.autofilter(0, 0, len(pagos), len(columnas) - 1)
