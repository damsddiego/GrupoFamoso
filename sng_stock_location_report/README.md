# sng_stock_location_report

## Reporte de Movimientos por Ubicación (Odoo 18)

Módulo para generar reportes detallados de movimientos de stock por ubicación, con soporte para múltiples almacenes, filtros por rango de fechas y exportación a Excel.

---

## Tabla de Contenidos

1. [Información General](#información-general)
2. [Estructura del Módulo](#estructura-del-módulo)
3. [Dependencias](#dependencias)
4. [Modelos](#modelos)
   - [stock.location.report](#stocklocationreport)
   - [stock.location.report.line](#stocklocationreportline)
5. [Vistas](#vistas)
6. [Seguridad](#seguridad)
7. [Controlador Web](#controlador-web)
8. [Flujo de Uso](#flujo-de-uso)
9. [Notas Técnicas](#notas-técnicas)

---

## Información General

| Atributo | Valor |
|----------|-------|
| **Nombre técnico** | `sng_stock_location_report` |
| **Versión** | 18.0.1.0.0 |
| **Categoría** | Inventory/Inventory |
| **Licencia** | LGPL-3 |
| **Autor** | SNG |
| **Aplicación** | No |

### Características principales

- Selección de **uno o más almacenes** (`Many2many`)
- Filtro opcional por **ubicación específica**
- Filtro por **rango de fechas**
- Visualización de **entradas**, **salidas** y **reservas** por producto
- **Totales** calculados automáticamente
- **Exportación a Excel** con 5 hojas
- Estados: `Borrador` → `Generado`

---

## Estructura del Módulo

```
sng_stock_location_report/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── stock_location_report.py      # Modelo principal
│   └── stock_location_report_line.py # Líneas del reporte
├── controllers/
│   ├── __init__.py
│   └── main.py                        # Exportación Excel
├── security/
│   ├── security.xml                   # Grupos
│   └── ir.model.access.csv           # Permisos
├── views/
│   ├── stock_location_report_views.xml      # Vistas reporte
│   └── stock_location_report_line_views.xml # Vistas líneas
└── wizard/
    └── __init__.py
```

---

## Dependencias

| Módulo | Descripción |
|--------|-------------|
| `base` | Núcleo de Odoo |
| `stock` | Gestión de inventario |
| `web` | Framework web |

---

## Modelos

### `stock.location.report`

Modelo principal del reporte. Almacena los filtros seleccionados y las líneas generadas.

#### Campos

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `name` | `Char` | Computado | Nombre automático: "Almacén1, Almacén2 - dd/mm/aaaa a dd/mm/aaaa" |
| `warehouse_ids` | `Many2many(stock.warehouse)` | Sí | Almacenes a incluir en el reporte |
| `location_id` | `Many2one(stock.location)` | No | Ubicación específica (filtra dentro de los almacenes) |
| `date_from` | `Date` | Sí | Fecha inicio del período (default: primer día del mes) |
| `date_to` | `Date` | Sí | Fecha fin del período (default: hoy) |
| `state` | `Selection` | Sí | `draft` (Borrador) / `generated` (Generado) |
| `line_ids` | `One2many` | — | Líneas de detalle por producto |
| `total_entradas` | `Float` | Computado | Suma de entradas de todas las líneas |
| `total_salidas` | `Float` | Computado | Suma de salidas de todas las líneas |
| `total_fisico` | `Float` | Computado | Suma de cantidad física |
| `total_reservado` | `Float` | Computado | Suma de cantidad reservada |
| `total_disponible` | `Float` | Computado | Suma de cantidad disponible |

#### Métodos principales

| Método | Descripción |
|--------|-------------|
| `action_generate_report()` | Genera las líneas del reporte y cambia estado a `generated` |
| `action_reset_to_draft()` | Elimina líneas y vuelve a estado `draft` |
| `action_export_excel()` | Redirige al endpoint de exportación Excel |
| `_get_location_domain()` | Retorna dominio de ubicaciones según filtros |
| `_generate_lines()` | Consulta SQL para obtener productos y crear líneas |
| `_get_product_line_vals()` | Calcula entradas, salidas, físico y reservado por producto |

#### Lógica de generación

1. Obtiene el dominio de ubicaciones:
   - Si hay `location_id`: solo esa ubicación
   - Si no: todas las ubicaciones internas de los almacenes seleccionados (`child_of`)

2. Consulta SQL para obtener productos únicos que tengan:
   - Movimientos de stock (`stock_move`) en el período y ubicaciones
   - O quants (`stock_quant`) con cantidad > 0

3. Por cada producto, ejecuta 3 consultas SQL:
   - **Entradas**: `SUM(quantity)` donde `location_dest_id IN` ubicaciones
   - **Salidas**: `SUM(quantity)` donde `location_id IN` ubicaciones
   - **Quants**: `SUM(quantity)` y `SUM(reserved_quantity)`

4. Crea líneas solo si hay datos distintos de cero.

---

### `stock.location.report.line`

Modelo de líneas de detalle. Cada línea representa un producto con sus cantidades.

#### Campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `report_id` | `Many2one(stock.location.report)` | Reporte padre |
| `product_id` | `Many2one(product.product)` | Producto |
| `default_code` | `Char` | Código interno del producto |
| `product_name` | `Char` | Nombre del producto |
| `uom_id` | `Many2one(uom.uom)` | Unidad de medida |
| `entradas_qty` | `Float` | Cantidad de entradas en el período |
| `salidas_qty` | `Float` | Cantidad de salidas en el período |
| `movimiento_net` | `Float` (compute) | `entradas_qty - salidas_qty` |
| `fisico_qty` | `Float` | Cantidad física actual (quants) |
| `reservado_qty` | `Float` | Cantidad reservada actual (quants) |
| `disponible_qty` | `Float` | `fisico_qty - reservado_qty` |

---

## Vistas

### Vistas del reporte (`stock.location.report`)

| Vista | XML ID | Tipo | Descripción |
|-------|--------|------|-------------|
| Form | `view_stock_location_report_form` | `form` | Filtros, totales y notebook con líneas |
| List | `view_stock_location_report_tree` | `list` | Listado de reportes con totales y badge de estado |
| Search | `view_stock_location_report_search` | `search` | Búsqueda y filtros por estado, agrupación |

### Vistas de líneas (`stock.location.report.line`)

| Vista | XML ID | Tipo | Descripción |
|-------|--------|------|-------------|
| List | `view_stock_location_report_line_tree` | `list` | Detalle por producto con sumatorias |
| Search | `view_stock_location_report_line_search` | `search` | Filtros por entradas/salidas/reservas |

### Acciones y menú

| Elemento | XML ID | Descripción |
|----------|--------|-------------|
| Acción | `action_stock_location_report` | Abre vista list/form del reporte |
| Menú | `menu_stock_location_report_root` | **Inventario > Informes > Reporte por Ubicación** |

---

## Seguridad

### Grupos

| Grupo | XML ID | Descripción |
|-------|--------|-------------|
| Manager | `group_stock_location_report_manager` | Acceso total. Hereda `stock.group_stock_user` |

### Permisos de acceso (`ir.model.access`)

| Modelo | Grupo | Lectura | Escritura | Creación | Eliminación |
|--------|-------|---------|-----------|----------|-------------|
| `stock.location.report` | `stock.group_stock_user` | ✅ | ✅ | ✅ | ❌ |
| `stock.location.report` | Manager | ✅ | ✅ | ✅ | ✅ |
| `stock.location.report.line` | `stock.group_stock_user` | ✅ | ❌ | ❌ | ❌ |
| `stock.location.report.line` | Manager | ✅ | ✅ | ✅ | ✅ |

---

## Controlador Web

### Endpoint

```
GET /stock_location_report/export/<int:report_id>
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `report_id` | `int` | ID del reporte a exportar |

**Requisitos**: Usuario autenticado, reporte en estado `generated`.

### Hojas del archivo Excel

| Hoja | Contenido |
|------|-----------|
| **Resumen** | Almacenes, fechas, totales (entradas, salidas, neto, físico, reservado, disponible) |
| **Detalle por Producto** | Código, nombre, UoM, entradas, salidas, neto, físico, reservado, disponible |
| **Entradas** | Movimientos de entrada (`location_dest_id` en ubicaciones, estado `done`) |
| **Salidas** | Movimientos de salida (`location_id` en ubicaciones, estado `done`) |
| **Reservas** | Quants actuales con cantidad o reserva > 0 |

### Formato

- Encabezados con fondo azul (`#366092`) y texto blanco
- Totales con fondo azul claro (`#B4C7E7`)
- Números con formato `#,##0.00`
- Anchos de columna ajustados

---

## Flujo de Uso

1. Ir a **Inventario > Informes > Reporte por Ubicación**
2. Click en **Nuevo**
3. Seleccionar **uno o más almacenes** (campo `warehouse_ids`)
4. (Opcional) Seleccionar una **ubicación específica**
5. Definir **rango de fechas**
6. Click en **"Generar Reporte"**
7. Revisar totales y detalle por producto
8. Click en **"Exportar a Excel"** para descargar el archivo

---

## Notas Técnicas

### Compatibilidad Odoo 18

- Las vistas usan `<list>` en lugar de `<tree>` (cambio en Odoo 18)
- El `view_mode` en acciones usa `list` en lugar de `tree`
- El campo `warehouse_ids` es `Many2many` para soportar múltiples almacenes

### Rendimiento

- Las consultas de movimientos usan SQL directo (`self._cr.execute`) para mejor rendimiento
- Se filtran solo productos con movimientos o stock en el período
- Las líneas se crean en batch (`create(lines_to_create)`)

### Restricciones

- La fecha `Desde` no puede ser mayor que la fecha `Hasta`
- No se pueden generar líneas si no hay ubicaciones para los criterios seleccionados
- La exportación a Excel requiere que el reporte esté en estado `generated`

### Tablas en base de datos

| Tabla | Descripción |
|-------|-------------|
| `stock_location_report` | Registros del reporte |
| `stock_location_report_line` | Líneas de detalle |
| `stock_location_report_stock_warehouse_rel` | Relación Many2many reporte-almacén |
