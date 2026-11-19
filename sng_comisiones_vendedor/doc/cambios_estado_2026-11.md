# Cambios en `obtener_estado` — noviembre 2026 (v18.0.2.0.0)

Para quien mantiene la app de ruteros («Mis comisiones»).

Desde `sng_sales_commission_payment` 18.0.6.0.0 la comisión del mes ya no es por
compañía sino por **cuadro de comisiones**, y un cuadro puede juntar varias
compañías. Por eso `sng.comision.estado.obtener_estado(vendedor_id, periodo)`
devuelve un resumen por comisión, con el desglose por compañía adentro.

Los cruces (`cruces.reportados`, `anulados`, `registrados_por_otro`,
`comision_de_otro`, `sin_comision`, `reversos`), `vendedor`, `periodo`,
`generado` y `totales` no cambiaron. Cada pago conserva su `compania_id` y
`compania`.

## Qué cambió

| Dónde | Antes | Ahora |
|---|---|---|
| `resumen[]` | una fila por compañía | una fila por comisión (cuadro) |
| `resumen[].compania_id` | id de la compañía | **eliminada** |
| `resumen[].compania` | nombre de la compañía | **eliminada**; usar `cuadro` |
| `resumen[].cuadro_id` | — | id del cuadro de comisiones |
| `resumen[].cuadro` | — | nombre del cuadro (p. ej. «Grupo Famoso») |
| `resumen[].mensual_id` | — | id del mensual en Odoo; `false` si todavía no existe |
| `resumen[].companias[]` | — | desglose por compañía (ver abajo) |
| `periodos[].estados[].compania` | nombre de la compañía | **renombrada** a `cuadro` |

Las demás claves de cada resumen siguen igual: `salesperson_id`, `vendedor`,
`estado`, `estado_texto`, `estimado`, `base`, `porcentaje`, `comision`,
`ajustes`, `en_proceso`, `siguiente_tramo` y `proyeccion`. Ahora `base`,
`porcentaje`, `siguiente_tramo` y `proyeccion` son sobre lo cobrado en todas
las compañías del cuadro.

## Ejemplo de un resumen de grupo

```json
{
  "mensual_id": 412,
  "cuadro_id": 6,
  "cuadro": "Grupo Famoso",
  "salesperson_id": 17,
  "vendedor": "EDUARDO RODRIGUEZ MAYORGA",
  "estado": "draft",
  "estado_texto": "Pendiente",
  "estimado": true,
  "base": 29144491.09,
  "porcentaje": 3.5,
  "comision": 1020057.19,
  "ajustes": 0.0,
  "en_proceso": 0.0,
  "siguiente_tramo": {"minimo": 35000000.0, "porcentaje": 4.0, "falta": 5855508.91},
  "proyeccion": null,
  "companias": [
    {"compania_id": 1, "compania": "GRUPO FAMOSO SOCIEDAD ANONIMA",
     "cobrado": 3467028.70, "base": 3068166.99, "comision": 107385.84, "ajustes": 0.0},
    {"compania_id": 2, "compania": "PROTIRE SOCIEDAD ANONIMA",
     "cobrado": 29466246.23, "base": 26076324.10, "comision": 912671.34, "ajustes": 0.0}
  ]
}
```

Los números del ejemplo son ilustrativos.

## Notas

- `companias[].comision` es la base de esa compañía por el porcentaje de la
  comisión completa. Es informativo: el tramo sale de la base total.
- La suma de `companias[].base` es igual a `base`. La suma de
  `companias[].comision` más la de `companias[].ajustes` es igual a `comision`,
  salvo céntimos de redondeo.
- Un resumen sin mensual todavía (solo cobros en proceso) trae
  `mensual_id: false` y `companias: []`.
- En los meses anteriores al cuadro de grupo cada compañía tenía su propio
  cuadro, así que un vendedor puede traer varios resúmenes, uno por cuadro.
- Un vendedor con contactos duplicados sigue trayendo un resumen por contacto.
