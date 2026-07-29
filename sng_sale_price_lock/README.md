# SNG Bloqueo de Precio y Descuento en Ventas

Bloqueo **duro** (validado en servidor) del precio unitario y del descuento en
las lineas de pedido de venta: si el valor no proviene de la lista de precios
del pedido, no se guarda.

## Como funciona

Antes de aceptar el guardado, el modulo vuelve a calcular lo que la lista de
precios diria para esa linea y lo compara contra lo que se intenta grabar:

| Concepto | Origen del valor esperado |
|---|---|
| Precio unitario | `_get_display_price()` + conversion de impuestos, igual que `_reset_price_unit()` de `sale` |
| Descuento | Regla `pricelist_item_id`; es 0 cuando la regla no es de tipo porcentaje o cuando no hubo regla |

La validacion vive en `create()` y `write()` de `sale.order.line`, **no** en un
`readonly` de vista. Eso significa que tambien aplica a:

- importaciones desde Excel/CSV,
- llamadas XML-RPC / JSON-RPC de apps externas,
- el asistente nativo de descuentos (`Descuento` en el pedido),
- Odoo Studio.

Los recalculos internos de Odoo pasan por `_write()` (flush de campos
calculados) y no por `write()`, por lo que no disparan falsos positivos.

## Configuracion

Ajustes → Ventas → *Precios*:

- **Bloquear precio fuera de la lista** — modo `Exacto` o
  `Permitir precios mayores, bloquear menores`.
- **Bloquear descuento fuera de la lista** — modo `Exacto` o
  `Permitir descuentos menores, bloquear mayores`.
- **Tolerancia (%)** — desviacion admitida antes de bloquear (0 = exacto).

Los tres ajustes son por compania.

## Excepcion

Grupo **Modificar precio/descuento fuera de la lista de precios**
(`sng_sale_price_lock.group_sng_force_price`). Quien lo tenga captura precios y
descuentos libremente y ademas ve el boton de descuento del pedido.

## Lineas que nunca se validan

Secciones y notas, anticipos, gastos reembolsables, combos, lineas ya
facturadas, gastos de envio (`delivery`), recompensas de `sale_loyalty` y la
linea de descuento global del asistente nativo.

## Escape para automatizaciones

```python
lines.with_context(sng_skip_price_lock=True).write({'price_unit': 123.0})
```

## Alcance

Solo `sale.order.line`. Las facturas (`account.move.line`) no se validan: una
factura creada desde el pedido hereda el precio ya validado, pero una factura
capturada a mano admite cualquier precio.
