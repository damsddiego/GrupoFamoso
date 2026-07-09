# Referencia Funcional — `sale_stock_sng`

Documentación técnica de todas las clases, campos y métodos que componen el módulo.

---

## `models/res_partner.py` — `ResPartner`

**Hereda:** `res.partner`

### Campos nuevos

| Campo | Tipo | Descripción |
|---|---|---|
| `sale_location_id` | `Many2one(stock.location)` | Ubicación interna asignada al cliente. Se usa como bodega de consignación y para calcular el inventario en sitio. |
| `team_id` | `Many2one(crm.team)` | Equipo de ventas asignado directamente al contacto (complementa el equipo de la orden de venta). |

---

## `models/sale_order.py` — `SaleOrder`

**Hereda:** `sale.order`

### Campos nuevos

| Campo | Tipo | Descripción |
|---|---|---|
| `partner_sale_location_id` | `Many2one(stock.location)` | Ubicación interna desde la que se forzará el despacho en esta orden. Solo editable en estado _Borrador_ o _Enviada_. |

### Métodos

#### `_onchange_partner_sale_location()`
- **Trigger:** `@api.onchange('partner_id')`
- Limpia `partner_sale_location_id` al cambiar de cliente.
- Si el partner tiene `team_id`, también actualiza el equipo de ventas de la orden.

#### `_prepare_procurement_values(group_id=False)`
- Sobrescribe el método estándar.
- Añade `partner_sale_location_id` al diccionario de valores de aprovisionamiento para que se propague hasta la `stock.rule`.

---

## `models/sale_order.py` — `SaleOrderLine`

**Hereda:** `sale.order.line`

### Métodos

#### `_get_location_final()`
- Retorna la ubicación de destino final para el cliente (usa `property_stock_customer` del contacto de envío o la ubicación genérica de clientes de Odoo).

#### `_prepare_procurement_values(group_id=False)`
- Propaga `partner_sale_location_id` desde la orden hacia los valores de procurement de cada línea.

---

## `models/stock_rule.py` — `StockRule`

**Hereda:** `stock.rule`

### Métodos

#### `_get_custom_move_fields()`
- Registra `partner_sale_location_id` como campo personalizado para que Odoo lo traslade automáticamente del procurement al `stock.move`.

#### `_get_stock_move_values(product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values)`
- Sobrescribe el método estándar.
- Si `values` contiene `partner_sale_location_id`, sobreescribe `location_id` del movimiento con esa ubicación.
- Incluye logging con `_logger.info` para trazabilidad.

---

## `models/stock_rule.py` — `ProcurementGroup`

**Hereda:** `procurement.group`

### Métodos

#### `run(procurements, raise_user_error=True)`
- Sobrescribe el método estándar.
- Agrega logging para productos con referencia `92001006` o ubicaciones que contengan "Traslado" — útil para depuración de consignaciones específicas.

---

## `models/stock_move.py` — `StockMove`

**Hereda:** `stock.move`

### Campos nuevos

| Campo | Tipo | Descripción |
|---|---|---|
| `partner_sale_location_id` | `Many2one(stock.location)` | Ubicación de consignación del cliente asociada a este movimiento. |

### Métodos

#### `_action_confirm(merge=True, merge_into=False)`
- Sobrescribe el método estándar.
- Antes de confirmar: si algún movimiento tiene `partner_sale_location_id`, fuerza `procure_method = 'make_to_stock'` para garantizar que el inventario se tome de la ubicación ya existente (no genera una orden de compra/fabricación).
- Añade logging detallado por movimiento.

---

## `models/stock_picking.py` — `StockPicking`

**Hereda:** `stock.picking`

### Métodos

#### `_onchange_partner_sale_locations()`
- **Trigger:** `@api.onchange('partner_id')`
- Solo aplica a transferencias de tipo **interno** (`picking_type_id.code == 'internal'`).
- Establece automáticamente:
  - `location_id`: bodega del vendedor asignado al partner (`partner.user_id.partner_id.sale_location_id`)
  - `location_dest_id`: bodega del cliente (`partner_id.sale_location_id`)

---

## `models/stock_quant.py` — `StockQuant`

**Hereda:** `stock.quant`

### Campos nuevos

| Campo | Tipo | Descripción |
|---|---|---|
| `in_my_location` | `Boolean` (computed, no-store) | `True` si el quant está en la bodega asignada al usuario actual (o en alguna ubicación hija). |

### Métodos

#### `_get_user_root_location()`
- Obtiene la ubicación raíz del usuario actual a partir de `env.user.partner_id.sale_location_id`.
- Soporta tanto `stock.warehouse` (devuelve `view_location_id`) como `stock.location`.

#### `_compute_in_my_location()`
- Calcula el campo `in_my_location` para cada quant usando `_is_child_of()` o búsqueda por `child_of`.

#### `_search_in_my_location(operator, value)`
- Permite usar el domain `[('in_my_location', '=', True/False)]` en búsquedas y filtros XML.
- Construye un domain equivalente con `child_of` hacia la ubicación raíz del usuario.

---

## `models/stock_return_picking.py` — `StockReturnPicking`

**Hereda:** `stock.return.picking`

### Métodos

#### `_prepare_picking_default_values_based_on(picking)`
- Sobrescribe el método estándar del wizard de devolución.
- Solo cambia el comportamiento cuando el picking original es de tipo **entrega** (`picking_type_code == 'outgoing'`).
- Define `location_dest_id` del picking de devolución como `picking.location_id`, es decir, la ubicación desde donde salió la entrega original.
- No modifica devoluciones de recepciones, transferencias internas u otros tipos de operación.

---

## `models/stock_return_picking.py` — `StockReturnPickingLine`

**Hereda:** `stock.return.picking.line`

### Métodos

#### `_prepare_move_default_values(new_picking)`
- Sobrescribe los valores por defecto de cada movimiento generado por el wizard.
- En devoluciones de entregas, define `location_dest_id` de la línea como `move_id.location_id`.
- Esto asegura que, si una entrega tuvo movimientos con ubicaciones origen distintas, cada línea de devolución vuelva a la ubicación exacta desde donde salió.

---

## `models/product.py` — `ProductTemplate`

**Hereda:** `product.template`

### Métodos

#### `_onchange_type_set_is_storable()`
- **Trigger:** `@api.onchange('type')`
- Si el usuario cambia el tipo de producto a `'consu'`, marca automáticamente `is_storable = True`.

---

## `wizards/consign_cxc_wizard.py` — `ConsignCxcWizard`

**Modelo:** `consign.cxc.wizard` (TransientModel)

### Campos

| Campo | Tipo | Descripción |
|---|---|---|
| `date_from` | `Date` | Fecha de inicio del rango del reporte (opcional). |
| `date_to` | `Date` | Fecha de corte del reporte (requerida; por defecto: hoy). |
| `location_ids` | `Many2many(stock.location)` | Bodegas internas a incluir. Si está vacío, incluye todas. |
| `user_id` | `Many2one(res.users)` | Filtro por vendedor. |

### Métodos

#### `_onchange_user_id_fill_locations()`
- **Trigger:** `@api.onchange('user_id')`
- Busca todos los clientes (`res.partner`) cuyo `user_id` coincida con el vendedor seleccionado.
- Rellena `location_ids` con el conjunto único de `sale_location_id` de esos clientes.

#### `_get_date_from_effective()`
- Retorna `date_from` si está definido, o `date(1970, 1, 1)` como valor genérico de inicio.

#### `action_print()`
- Valida que `date_to` esté definido y que `date_from <= date_to`.
- Lanza la acción del reporte XLSX (`sale_stock_sng.consign_cxc_report_xlsx_action`).

---

## `wizards/consign_cxc_xlsx.py` — `ConsignCxcXlsx`

**Modelo:** `report.sale_stock_sng.consign_cxc_xlsx` (AbstractModel)  
**Hereda:** `report.report_xlsx.abstract`

### Helpers — Ubicaciones

#### `_partner_root_location(partner)`
- Retorna la ubicación raíz del cliente: primero `sale_location_id`, luego `property_stock_customer`.

#### `_location_allowed_by_wizard(root_loc, wiz_locations)`
- Retorna `True` si la ubicación del cliente está dentro de las bodegas seleccionadas en el wizard (o si no se seleccionó ninguna).

### Helpers — Stock / Valor

#### `_valued_stock_now(partner, wiz_locations=None)`
- Calcula el **valor total del inventario** actualmente en la bodega del cliente.
- Suma `quant.quantity * product.standard_price` de todos los quants en la ubicación del partner filtrados por las bodegas del wizard.

#### `_last_movement_date_in_partner_location(partner, lower_dt, upper_dt, wiz_locations=None)`
- Retorna la fecha del **último movimiento de inventario** (`stock.move.line` en estado `done`) que tocó la bodega del cliente dentro del rango de fechas indicado.

### Helpers — Ventas / CxC

#### `_last_sale_or_refund_date(partner, lower_d, upper_d)`
- Retorna la fecha de la **última factura o nota de crédito** confirmada del cliente dentro del período.

#### `_partner_pending_balance(partner, lower_d, upper_d)`
- Calcula el **saldo pendiente de cobro (CxC)** sumando `amount_residual_signed` de todas las facturas/NTC confirmadas del cliente en el período.

#### `_partner_credit_limit(partner)`
- Retorna el **límite de crédito** del cliente. Intenta leer los campos `credit_limit`, `x_credit_limit` o `property_credit_limit` según disponibilidad.

#### `_partner_fpp_trimestral(partner)`
- Retorna el **nombre del término de pago** asignado al cliente (`property_payment_term_id`).

### Helpers — Detección de Fechas

#### `_detect_min_date(partners)`
- Detecta automáticamente la **primera fecha de actividad** de los partners (primera transferencia hecha o primera factura posteada).

### Helpers — Moneda

#### `_safe_ref(xmlid)`
- Retorna el objeto referenciado por el `xmlid` o `False` si no existe.

#### `_convert(amount, from_currency, to_currency, conv_date)`
- Convierte un monto entre monedas usando el tipo de cambio de la empresa a la fecha indicada.

### Método Principal

#### `generate_xlsx_report(workbook, data, wizards)`
- Genera la hoja Excel **"Consignaciones y CxC"** con:

  **Encabezado:**
  - Título del reporte, fecha/hora de generación, filtros aplicados.

  **Columnas de datos por cliente:**

  | # | Columna | Fuente |
  |---|---|---|
  | 1 | Cod cliente | `client_code` / `vat` / `id` |
  | 2 | Cliente | `partner.name` |
  | 3 | Bodega cliente | `sale_location_id.complete_name` |
  | 4 | Vendedor | `user_id.name` |
  | 5 | RUTA/ZONA | `team_id.name` |
  | 6 | Último traslado bodega cliente | `_last_movement_date_in_partner_location()` |
  | 7 | Última venta o NTC | `_last_sale_or_refund_date()` |
  | 8 | Consignado Colones | `_valued_stock_now()` → CRC |
  | 9 | Consignado Dólares | `_valued_stock_now()` → USD |
  | 10 | CXC Colones | `_partner_pending_balance()` → CRC |
  | 11 | CXC Dólares | `_partner_pending_balance()` → USD |
  | 12 | GENERAL Colones | Consignado + CXC → CRC |
  | 13 | GENERAL Dólares | Consignado + CXC → USD |
  | 14 | Límite de crédito | `_partner_credit_limit()` |
  | 15 | Saldo pendiente | `_partner_pending_balance()` (moneda empresa) |
  | 16 | FPP trimestral | `_partner_fpp_trimestral()` |

  **Fila de totales:** Suma de columnas 8–13.  
  **Presentación:** Anchos de columna optimizados, encabezado fijo (`freeze_panes`), autofilter activado.

---

## Flujo Completo — Consignación

```
Orden de Venta
  └─ partner_sale_location_id (bodega de consignación)
       │
       ▼
  SaleOrder._prepare_procurement_values()
       │
       ▼
  SaleOrderLine._prepare_procurement_values()
       │
       ▼
  StockRule._get_stock_move_values()
       │  → sobreescribe location_id con partner_sale_location_id
       ▼
  StockMove._action_confirm()
       │  → fuerza procure_method = 'make_to_stock'
       ▼
  Picking generado toma mercancía
  directamente de la bodega del cliente
```
