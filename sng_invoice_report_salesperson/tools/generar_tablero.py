#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera data/files/invoicing_dashboard.json a partir del tablero
«Facturación» de Odoo Enterprise (spreadsheet_dashboard_account),
cambiando el vendedor usuario (invoice_user_id / res.users) por el vendedor
contacto de sales_commission_omax (salesperson_id / res.partner).

Uso (desde cualquier carpeta):

    python3 tools/generar_tablero.py [ruta/al/invoicing_dashboard.json de Odoo]

Si no se indica ruta, se toma odoo18e/spreadsheet_dashboard_account/data/
files/invoicing_dashboard.json relativo a /opt/odoo18. No depende de Odoo.
"""
import json
import re
import sys
from pathlib import Path

FILTRO_VENDEDOR = "02acc7f7-b282-4ce9-bf38-6abfb72be6aa"
PIVOTE_VENDEDORES = "4"
LISTA_FACTURAS = "1"
CAMPO_USUARIO = "invoice_user_id"
CAMPO_VENDEDOR = "salesperson_id"

AQUI = Path(__file__).resolve().parent
ORIGEN_POR_DEFECTO = Path(
    "/opt/odoo18/odoo18e/spreadsheet_dashboard_account/data/files/invoicing_dashboard.json"
)
DESTINO = AQUI.parent / "data" / "files" / "invoicing_dashboard.json"


def cambiar_filtro(datos):
    filtro = next(f for f in datos["globalFilters"] if f["id"] == FILTRO_VENDEDOR)
    assert filtro["modelName"] == "res.users", filtro
    filtro["modelName"] = "res.partner"
    filtro["domainOfAllowedValues"] = [["is_salesperson", "=", True]]


def cambiar_field_matching(field_matching):
    coincidencia = field_matching.get(FILTRO_VENDEDOR)
    if coincidencia and coincidencia["chain"] == CAMPO_USUARIO:
        coincidencia["chain"] = CAMPO_VENDEDOR


def cambiar_pivotes(datos):
    for pivote in datos["pivots"].values():
        cambiar_field_matching(pivote.get("fieldMatching", {}))
    vendedores = datos["pivots"][PIVOTE_VENDEDORES]
    assert vendedores["rows"] == [{"fieldName": CAMPO_USUARIO}], vendedores["rows"]
    vendedores["rows"] = [{"fieldName": CAMPO_VENDEDOR}]
    vendedores["domain"] = [
        [CAMPO_VENDEDOR, cond[1], cond[2]]
        if isinstance(cond, list) and cond[0] == CAMPO_USUARIO else cond
        for cond in vendedores["domain"]
    ]


def cambiar_listas(datos):
    for lista in datos.get("lists", {}).values():
        cambiar_field_matching(lista.get("fieldMatching", {}))
    lista = datos["lists"][LISTA_FACTURAS]
    if CAMPO_VENDEDOR not in lista["columns"]:
        lista["columns"].append(CAMPO_VENDEDOR)


def cambiar_celdas(datos):
    patron_pivote = re.compile(r'"#%s"' % CAMPO_USUARIO)
    patron_lista = re.compile(r'ODOO\.LIST\((\d+),(\d+),"user_id"\)')
    for hoja in datos["sheets"]:
        for figura in hoja.get("figures", []):
            if figura["tag"] == "chart":
                cambiar_field_matching(figura["data"].get("fieldMatching") or {})
        for celda in hoja.get("cells", {}).values():
            contenido = celda.get("content")
            if not contenido:
                continue
            contenido = patron_pivote.sub('"#%s"' % CAMPO_VENDEDOR, contenido)
            contenido = patron_lista.sub(
                r'ODOO.LIST(\1,\2,"%s")' % CAMPO_VENDEDOR, contenido
            )
            if "odoo://view/" in contenido:
                # Enlace «Top Salespeople»: acción pivote con dominio y
                # agrupación por el campo del vendedor.
                contenido = contenido.replace(
                    '"%s"' % CAMPO_USUARIO, '"%s"' % CAMPO_VENDEDOR
                )
            celda["content"] = contenido


def generar(origen: Path, destino: Path):
    datos = json.loads(origen.read_text(encoding="utf-8"))
    cambiar_filtro(datos)
    cambiar_pivotes(datos)
    cambiar_listas(datos)
    cambiar_celdas(datos)
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    assert CAMPO_USUARIO not in texto, "quedan referencias a invoice_user_id"
    assert "res.users" not in texto, "quedan referencias a res.users"
    assert '"user_id"' not in texto, "quedan referencias a user_id"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return texto


if __name__ == "__main__":
    origen = Path(sys.argv[1]) if len(sys.argv) > 1 else ORIGEN_POR_DEFECTO
    texto = generar(origen, DESTINO)
    print(f"Generado {DESTINO} ({len(texto)} bytes) desde {origen}")
