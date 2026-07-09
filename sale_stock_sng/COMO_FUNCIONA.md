# Cómo Funciona `sale_stock_sng`

## Objetivo del módulo

`sale_stock_sng` extiende el flujo estándar de **Ventas + Inventario + Facturación** de Odoo para trabajar mejor con clientes que manejan **inventario en consignación** y para agregar utilidades operativas alrededor de ese proceso.

En términos prácticos, el módulo hace cinco cosas principales:

1. Permite definir una **bodega interna asociada al cliente**.
2. Permite forzar desde la orden de venta la **ubicación interna real de salida**.
3. Hace que esa ubicación se propague hasta los **movimientos de stock**.
4. Hace que las **devoluciones de entregas** regresen por defecto a la ubicación desde donde salió la entrega.
5. Agrega herramientas de consulta:
   - filtro **Mi bodega** en quants,
   - reporte XLSX de **Consignaciones y CxC**,
   - precios y total en el **delivery slip**.

---

## Dependencias funcionales

El módulo depende de:

- `sale_stock`: base del flujo venta -> entrega.
- `account`: facturas y notas de crédito.
- `report_xlsx`: generación del Excel.
- `partner_client_code`: código de cliente usado en el reporte.
- `cr_electronic_invoice`: facturación electrónica Costa Rica.

---

## Flujo principal de consignación

### 1. Configuración del cliente

En `res.partner` se agregan dos campos:

- `sale_location_id`: ubicación interna asignada al cliente.
- `team_id`: equipo comercial asociado al cliente.

Esto permite que cada cliente tenga una bodega interna propia para operar consignación.

Archivo relacionado:

- `models/res_partner.py`
- `views/res_partner_views.xml`

### 2. Orden de venta

En `sale.order` se agrega el campo:

-`: ubicación de salida que se quiere usar en esa orden.

Comportamiento:

- Al cambiar el cliente, el campo se limpia.
- Si el cliente tiene `team_id`, la orden toma ese equipo de ventas.
- El campo queda de solo lectura cuando la orden deja de estar en `draft` o `sent`.

Archivo relacionado:

- `models/sale_order.py`
- `views/sale_order_views.xml`

### 3. Propagación a procurement y stock

El valor de `partner_sale_location_id` no se queda solo en la orden. El módulo lo empuja hacia abajo en la cadena logística:

1. `sale.order` y `sale.order.line` agregan `partner_sale_location_id` a los valores de procurement.
2. `stock.rule` registra ese campo como campo custom del movimiento.
3. `stock.rule` sobrescribe `location_id` del `stock.move` con esa ubicación.
4. `stock.move` detecta movimientos de consignación y les fuerza `procure_method = 'make_to_stock'`.

Resultado:

- la salida se toma desde la ubicación interna indicada,
- no desde la ubicación estándar del almacén,
- y se evita que Odoo intente reaprovisionar como si fuera un flujo normal de compra/fabricación.

Archivos relacionados:

- `models/sale_order.py`
- `models/stock_rule.py`
- `models/stock_move.py`

---

## Transferencias internas desde el picking

En `stock.picking`, cuando el picking es de tipo `internal` y se selecciona un cliente:

- `location_id` se llena con la bodega del vendedor del cliente.
- `location_dest_id` se llena con la bodega asignada al cliente (`partner.sale_location_id`).

Esto acelera los traslados entre bodegas de consignación sin tener que definir manualmente origen y destino cada vez.

Archivo relacionado:

- `models/stock_picking.py`

---

## Ubicación destino en devoluciones de entregas

Cuando se usa el wizard estándar de Odoo para devolver una orden de entrega, el módulo ajusta el destino de la devolución para que vuelva a la ubicación desde donde salió la entrega original.

Comportamiento:

- Solo aplica a pickings de salida (`outgoing`).
- El encabezado de la devolución toma como destino `picking.location_id`.
- Cada línea generada toma como destino `move_id.location_id`.
- Si una entrega salió de una bodega de consignación o de una ubicación interna específica, la devolución regresa a esa misma ubicación.
- No cambia el comportamiento de recepciones, transferencias internas u otros tipos de operación.

Este ajuste aplica a devoluciones hechas desde el botón de devolución de la entrega.

Archivo relacionado:

- `models/stock_return_picking.py`

---

## Filtro "Mi bodega" en inventario

En `stock.quant` se agrega el campo calculado `in_my_location`.

La lógica usa `env.user.partner_id.sale_location_id` como raíz y marca el quant como verdadero si la ubicación del quant:

- es esa misma ubicación, o
- es una ubicación hija.

Luego se expone un filtro de búsqueda:

- **Mi bodega**

Esto permite que cada usuario vea más rápido el inventario de su bodega asignada.

Archivos relacionados:

- `models/stock_quant.py`
- `views/stock_quant_views.xml`

---

## Reporte XLSX de Consignaciones y CxC

El módulo incluye un wizard y un reporte Excel accesible desde:

- `Ventas -> Informes -> Reportes Personalizados -> Consignaciones y CxC`

### Wizard

El wizard `consign.cxc.wizard` permite filtrar por:

- `date_from`
- `date_to`
- `user_id`
- `location_ids`

Si se selecciona un vendedor, el wizard intenta llenar automáticamente las bodegas con base en los clientes asignados a ese vendedor.

### Qué calcula el reporte

Por cliente, el XLSX obtiene:

- código de cliente,
- cliente,
- bodega del cliente,
- vendedor,
- ruta/zona,
- último movimiento en la bodega,
- última venta o nota de crédito,
- valor del inventario consignado,
- saldo pendiente de CxC,
- total general,
- límite de crédito,
- término de pago.

### Cómo calcula los montos

- **Consignado**: suma `stock.quant.quantity * product.standard_price` dentro de la bodega del cliente.
- **CxC**: suma `amount_residual_signed` de facturas y NC posteadas.
- **General**: consignado + CxC.
- También convierte montos a **CRC** y **USD** usando la moneda de la compañía y la fecha `date_to`.

Archivos relacionados:

- `wizards/consign_cxc_wizard.py`
- `wizards/consign_cxc_xlsx.py`
- `wizards/consign_cxc_wizard_views.xml`
- `wizards/reports.xml`

---

## Cambios en el delivery slip

El reporte de entrega estándar de inventario se modifica para:

- usar un `paperformat` propio,
- mostrar logo y datos de empresa en el encabezado,
- mostrar precios unitarios y subtotales en líneas,
- mostrar total del documento,
- mostrar contacto en pickings internos.

Además, `stock.move.line` recalcula los agregados para que en entregas agrupadas también aparezcan:

- `price_unit`
- `subtotal`

Archivos relacionados:

- `report/stock_deliveryslip_report.xml`
- `models/stock_move_line.py`
- `models/stock_picking.py`

---

## Otros ajustes

### Producto consumible marcado como almacenable

En `product.template`, si el usuario cambia `type` a `consu`, el módulo marca `is_storable = True`.

Ese ajuste parece orientado a mantener productos consumibles dentro de un flujo donde igual se requiere manejo de existencias.

Archivo relacionado:

- `models/product.py`

### Logs de trazabilidad

El módulo agrega logs en:

- `stock.rule`
- `procurement.group`
- `stock.move`

Esto sirve para depurar problemas de ubicación o movimientos especiales de consignación.

---

## Resumen funcional

Si se mira el módulo como proceso completo, el comportamiento es este:

1. Se asigna una bodega interna al cliente.
2. En la orden de venta se puede indicar desde qué bodega cliente debe salir el producto.
3. Esa ubicación se propaga hasta el movimiento de stock real.
4. Los usuarios pueden filtrar inventario por su propia bodega.
5. Las devoluciones de entregas regresan por defecto a la ubicación de origen de la entrega.
6. El área comercial obtiene un Excel con inventario consignado y cuentas por cobrar por cliente.
7. Los delivery slips muestran información económica adicional.

En resumen, `sale_stock_sng` convierte el flujo estándar de Odoo en un flujo más orientado a **consignación, control por bodega de cliente y seguimiento comercial/contable**.
