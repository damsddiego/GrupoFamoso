# -*- coding: utf-8 -*-
"""Litros por unidad a partir del nombre de un valor del atributo de volumen.

Lógica pura (sin Odoo). Los valores se escriben a mano («1L», «60 L», «400ml»,
«ESTAÑÓN»), así que esto solo propone el número: el dato que manda es el campo
«Litros por unidad» del valor, editable en Comercial > Configuración.
"""
import re

LITROS_ESTANON = 208.0

_CON_UNIDAD = re.compile(r'(\d+(?:\.\d+)?)\s*(ml|lts?|litros?|l)\b')
_SOLO_NUMERO = re.compile(r'\d+(?:\.\d+)?')


def litros_desde_texto(texto):
    """«1L» → 1, «60 L» → 60, «400ml» → 0.4, «LIQ FRENO 250 ml» → 0.25,
    «1.2» → 1.2, «ESTAÑÓN» → 208. Lo que no es un volumen (BOMBA, LONAS) → 0."""
    texto = (texto or '').strip().lower().replace(',', '.')
    if not texto:
        return 0.0
    if 'estañ' in texto or 'estan' in texto:
        return LITROS_ESTANON
    con_unidad = _CON_UNIDAD.search(texto)
    if con_unidad:
        numero = float(con_unidad.group(1))
        return numero / 1000.0 if con_unidad.group(2) == 'ml' else numero
    if _SOLO_NUMERO.fullmatch(texto):
        return float(texto)
    return 0.0
