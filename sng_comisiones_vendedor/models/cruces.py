# -*- coding: utf-8 -*-
"""Cruces de «Mis comisiones».

Lógica pura (sin Odoo): recibe diccionarios ya leídos y arma el estado que ve
el vendedor. El modelo ``sng.comision.estado`` junta los datos con el ORM y el
script de prototipo los junta por RPC; los dos pasan por aquí, así que las
reglas son las mismas en la app, en el asistente de oficina y en las pruebas.

Entradas (todas con tipos JSON simples):

- ``pagos``: {id: pago}. Un pago trae ``id, nombre, recibo, fecha,
  fecha_confirmacion, cliente, compania_id, compania, monto, estado,
  verificado, de_app, vendedor_id, vendedor, creado_por, observaciones,
  facturas, dup_estado, monto_atipico, ia_estado, conciliado, comision_de,
  anulado_por, anulado_el``. ``comision_de`` es {vendedor_id: nombre} de las
  líneas de comisión del pago (de cualquier mes).
- ``lineas``: líneas de comisión de los mensuales del vendedor en el periodo:
  ``payment_id, compania_id, line_type, base, ajuste, motivo_reverso,
  periodo_original``.
- ``mensuales``: ``compania_id, compania, estado, base, porcentaje, comision,
  ajustes``.
- ``tramos``: {compania_id: [(monto_minimo, porcentaje), ...]}.
- ``pendientes``: pares (pago, factura) cobrados en el mes que todavía no
  tienen línea: ``payment_id, compania_id, compania, salesperson_id, base``.
- ``reemplazos``: {id del pago anulado: pago que lo reemplazó}.
"""

ESTADOS_PAGO = {
    'draft': 'No aplicado',
    'in_process': 'En proceso',
    'paid': 'Pagado',
    'canceled': 'Anulado',
    'rejected': 'Rechazado',
}
ESTADOS_MES = {
    'draft': 'Pendiente',
    'closed': 'Cerrado',
    'billed': 'Facturado',
    'paid': 'Pagado',
}
ANULADOS = ('canceled', 'rejected')
ACTIVOS = ('in_process', 'paid')
PREFIJO_FERIA = 'Venta de feria:'
IA = {
    'pendiente': 'buscando la factura',
    'sugerido': 'factura sugerida, falta confirmarla',
    'sin_match': 'no se encontró la factura',
    'error': 'error al buscar la factura',
}
MOTIVO_REVERSO = {
    'canceled': 'Pago anulado',
    'unreconciled': 'Pago desconciliado de la factura',
}


def registrado_por(pago, vendedor_id):
    """Quién registró el pago, visto desde el vendedor."""
    if not pago.get('de_app'):
        return {'tipo': 'oficina', 'nombre': 'Oficina · %s' % (pago.get('creado_por') or '?')}
    if not pago.get('vendedor_id'):
        return {'tipo': 'app_sin_vendedor', 'nombre': 'App sin vendedor'}
    if pago['vendedor_id'] == vendedor_id:
        return {'tipo': 'yo', 'nombre': 'Yo'}
    return {'tipo': 'vendedor', 'nombre': pago.get('vendedor') or '?'}


def tramo(tramos, compania_id, base):
    """(porcentaje alcanzado, siguiente tramo o None) para la base."""
    escala = sorted(tramos.get(compania_id) or [])
    porcentaje, siguiente = 0.0, None
    for minimo, pct in escala:
        if base >= minimo:
            porcentaje = pct
        elif siguiente is None:
            siguiente = {'minimo': minimo, 'porcentaje': pct, 'falta': round(minimo - base, 2)}
    return porcentaje, siguiente


def clase_reportado(pago):
    estado = pago['estado']
    if estado == 'canceled':
        return 'anulado'
    if estado == 'rejected':
        return 'rechazado'
    if estado == 'draft':
        return 'no_aplicado'
    return 'verificado' if pago.get('verificado') else 'sin_verificar'


def item(pago, vendedor_id, **extra):
    """Pago tal como lo muestra la app."""
    datos = {
        'id': pago['id'],
        'nombre': pago.get('nombre') or '',
        'recibo': pago.get('recibo') or '',
        'fecha': pago.get('fecha') or '',
        'fecha_confirmacion': pago.get('fecha_confirmacion') or '',
        'cliente': pago.get('cliente') or '',
        'compania': pago.get('compania') or '',
        'monto': round(pago.get('monto') or 0.0, 2),
        'estado': pago['estado'],
        'estado_texto': ESTADOS_PAGO.get(pago['estado'], pago['estado']),
        'verificado': bool(pago.get('verificado')),
        'registrado_por': registrado_por(pago, vendedor_id),
        'facturas': list(pago.get('facturas') or []),
    }
    datos.update(extra)
    return datos


def motivo_sin_comision(pago, filas_pendientes, vendedor_id):
    """Por qué un pago activo del vendedor todavía no tiene comisión."""
    if not pago.get('conciliado'):
        detalle = IA.get(pago.get('ia_estado') or '')
        return 'Sin factura ligada' + (' (%s)' % detalle if detalle else '')
    if pago.get('dup_estado') in ('sospecha', 'probable'):
        return 'Revisión de posible duplicado en oficina'
    if pago.get('monto_atipico'):
        return 'Monto atípico, revisión en oficina'
    if any(f.get('salesperson_id') == vendedor_id for f in filas_pendientes):
        return 'En proceso: la comisión se genera pronto'
    if filas_pendientes and all(not f.get('salesperson_id') for f in filas_pendientes):
        return 'La factura no tiene vendedor asignado'
    return 'Factura excluida de comisión o pendiente de revisión en oficina'


def _orden(pagos):
    return sorted(pagos, key=lambda p: (p.get('fecha') or '', p.get('id') or 0), reverse=True)


def _grupo(pagos, **extra):
    datos = {
        'cantidad': len(pagos),
        'monto': round(sum(p['monto'] for p in pagos), 2),
        'pagos': _orden(pagos),
    }
    datos.update(extra)
    return datos


def armar_estado(vendedor_id, vendedor_nombre, periodo, mensuales, lineas, pagos,
                 reportados_ids, tramos, pendientes, reemplazos,
                 periodos=None, generado=None):
    """Estado de comisiones del vendedor para un mes (dict listo para JSON)."""
    lineas = list(lineas or [])
    comisiones = [l for l in lineas if l['line_type'] == 'commission']
    base_por_pago = {}
    for l in comisiones:
        base_por_pago[l['payment_id']] = base_por_pago.get(l['payment_id'], 0.0) + l['base']

    # Resumen por compañía
    resumen = {}
    for m in mensuales:
        pct, siguiente = tramo(tramos, m['compania_id'], m['base'])
        resumen[m['compania_id']] = {
            'compania_id': m['compania_id'],
            'compania': m['compania'],
            'estado': m['estado'],
            'estado_texto': ESTADOS_MES.get(m['estado'], m['estado']),
            'estimado': m['estado'] == 'draft',
            'base': round(m['base'], 2),
            'porcentaje': m['porcentaje'],
            'comision': round(m['comision'], 2),
            'ajustes': round(m['ajustes'], 2),
            'en_proceso': 0.0,
            'siguiente_tramo': siguiente,
            'proyeccion': None,
        }
    en_proceso_por_pago = {}
    for f in pendientes:
        if f.get('salesperson_id') != vendedor_id or (f.get('base') or 0) <= 0:
            continue
        cid = f['compania_id']
        if cid not in resumen:
            _pct, siguiente = tramo(tramos, cid, 0.0)
            resumen[cid] = {
                'compania_id': cid, 'compania': f.get('compania') or '', 'estado': 'draft',
                'estado_texto': ESTADOS_MES['draft'], 'estimado': True, 'base': 0.0,
                'porcentaje': 0.0, 'comision': 0.0, 'ajustes': 0.0, 'en_proceso': 0.0,
                'siguiente_tramo': siguiente, 'proyeccion': None,
            }
        resumen[cid]['en_proceso'] += f['base']
        en_proceso_por_pago[f['payment_id']] = en_proceso_por_pago.get(f['payment_id'], 0.0) + f['base']
    for r in resumen.values():
        r['en_proceso'] = round(r['en_proceso'], 2)
        if r['en_proceso'] and r['estado'] == 'draft':
            base = r['base'] + r['en_proceso']
            pct, siguiente = tramo(tramos, r['compania_id'], base)
            r['proyeccion'] = {
                'base': round(base, 2),
                'porcentaje': pct,
                'comision': round(base * pct / 100.0 + r['ajustes'], 2),
                'siguiente_tramo': siguiente,
            }

    # Cruces
    reportados = [pagos[i] for i in reportados_ids if i in pagos]
    por_estado = {k: 0 for k in ('verificado', 'sin_verificar', 'no_aplicado', 'anulado', 'rechazado')}
    items_reportados = []
    for p in reportados:
        clase = clase_reportado(p)
        por_estado[clase] += 1
        items_reportados.append(item(p, vendedor_id, clase=clase,
                                     base=round(base_por_pago.get(p['id'], 0.0), 2)))

    anulados = []
    for p in reportados:
        if p['estado'] not in ANULADOS:
            continue
        extra = {'anulado_por': p.get('anulado_por') or '', 'anulado_el': p.get('anulado_el') or ''}
        if (p.get('observaciones') or '').strip().startswith(PREFIJO_FERIA):
            anulados.append(item(p, vendedor_id, clase='feria',
                                 detalle='Pago automático de feria', **extra))
        elif p['id'] in reemplazos:
            q = reemplazos[p['id']]
            anulados.append(item(p, vendedor_id, clase='rehecho', detalle='Rehecho con %s' % (q.get('nombre') or ''),
                                 reemplazo=item(q, vendedor_id), **extra))
        else:
            anulados.append(item(p, vendedor_id, clase='sin_reemplazo', detalle='Anulado sin reemplazo', **extra))

    por_otro, quienes = [], {}
    for pid, base in base_por_pago.items():
        p = pagos.get(pid)
        if not p:
            continue
        quien = registrado_por(p, vendedor_id)
        if quien['tipo'] == 'yo':
            continue
        por_otro.append(item(p, vendedor_id, base=round(base, 2)))
        clave = (quien['tipo'], quien['nombre'])
        q = quienes.setdefault(clave, {'tipo': quien['tipo'], 'nombre': quien['nombre'], 'cantidad': 0, 'base': 0.0})
        q['cantidad'] += 1
        q['base'] += base
    por_quien = sorted(({**q, 'base': round(q['base'], 2)} for q in quienes.values()),
                       key=lambda q: -q['base'])

    de_otro, sin_comision = [], []
    for p in reportados:
        if p['estado'] not in ACTIVOS:
            continue
        duenos = p.get('comision_de') or {}
        if duenos and vendedor_id not in duenos:
            de_otro.append(item(p, vendedor_id, comision_a=', '.join(sorted(duenos.values()))))
        elif not duenos:
            filas = [f for f in pendientes if f['payment_id'] == p['id']]
            sin_comision.append(item(p, vendedor_id, motivo=motivo_sin_comision(p, filas, vendedor_id),
                                     base=round(en_proceso_por_pago.get(p['id'], 0.0), 2)))

    reversos = []
    for l in lineas:
        if l['line_type'] != 'reversal':
            continue
        p = pagos.get(l['payment_id'])
        if not p:
            continue
        reversos.append(item(p, vendedor_id,
                             motivo=MOTIVO_REVERSO.get(l.get('motivo_reverso') or '', 'Reverso'),
                             periodo_original=l.get('periodo_original') or '',
                             ajuste=round(l.get('ajuste') or 0.0, 2)))

    companias = sorted(resumen.values(), key=lambda r: -r['base'])
    return {
        'vendedor': {'id': vendedor_id, 'nombre': vendedor_nombre},
        'periodo': periodo,
        'generado': generado or '',
        'periodos': periodos or [],
        'resumen': companias,
        'totales': {
            'base': round(sum(r['base'] for r in companias), 2),
            'comision': round(sum(r['comision'] for r in companias), 2),
            'en_proceso': round(sum(r['en_proceso'] for r in companias), 2),
        },
        'cruces': {
            'reportados': _grupo(items_reportados, por_estado=por_estado),
            'anulados': _grupo(anulados,
                               rehechos=sum(1 for a in anulados if a['clase'] == 'rehecho'),
                               feria=sum(1 for a in anulados if a['clase'] == 'feria'),
                               sin_reemplazo=sum(1 for a in anulados if a['clase'] == 'sin_reemplazo')),
            'registrados_por_otro': _grupo(por_otro, base=round(sum(p['base'] for p in por_otro), 2),
                                           por_quien=por_quien),
            'comision_de_otro': _grupo(de_otro),
            'sin_comision': _grupo(sin_comision),
            'reversos': _grupo(reversos, ajuste=round(sum(r['ajuste'] for r in reversos), 2)),
        },
    }
