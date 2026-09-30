# SNG Ubicaciones no disponibles para venta

Agrega a las ubicaciones de inventario la casilla **No disponible para venta**.
El stock de una ubicación marcada —y de todo lo que cuelga de ella— deja de
contarse como disponible **en las apps de SNG** (escritorio y móvil).

## Por qué

Al consultar existencias por almacén, Odoo suma todas las ubicaciones del
almacén. En Principal eso incluye `INVEN/Malo`: medido en septiembre de 2026,
99 productos aparecían con stock en la app sin tener una sola unidad vendible.

## Cómo funciona

- Se marcan las **pocas** ubicaciones que no cuentan. Todo lo demás cuenta por
  defecto, así que una ubicación nueva nunca queda oculta por olvido.
- Marcar la ubicación vista de un almacén excluye el almacén completo.
- El filtro **solo aplica si la consulta trae la clave de contexto**
  `sng_excluir_no_disponible`. La interfaz web de Odoo, las reservas, el
  reabastecimiento y la valoración no cambian.
- Afecta `qty_available`, `free_qty` y las entradas/salidas previstas. Un
  movimiento de Malo a Existencias cuenta como entrada, y uno de Existencias a
  Malo como salida, que es lo que son desde el punto de vista de la venta.
- No cambia de dónde reservan las entregas.

## Para las apps

Mandar `sng_excluir_no_disponible: true` en el contexto de las consultas de
producto. La app de escritorio lo hace en `OdooConnector._inject_default_context`.

## Advertencia para código del servidor

La clave no forma parte de la llave de caché de los campos de cantidad. Dentro de
una misma transacción, no leer el mismo producto con y sin la clave sin llamar a
`env.invalidate_all()` entre medio. Por RPC no aplica: cada llamada es una
transacción nueva.

## Compatibilidad

Se encadena con `stock_warehouse_security` (OCA): trabaja sobre el resultado de
`_get_domain_locations_new` y no sobre las ubicaciones de entrada, así que no
importa el orden de carga.
