# SNG Control Sale — Uso de la Alerta de Stock y Reservas

## 1. ¿Cuándo salta la alerta de "no hay stock"?

La alerta se dispara **al intentar confirmar una orden de venta** (pasar de *Cotización* a *Orden de Venta*), siempre y cuando la validación de stock esté activa en la compañía.

### Flujo de la validación

```
Cotización → Confirmar → ¿Hay stock suficiente?
                                │
                    ┌───────────┴───────────┐
                    │                       │
                   SÍ                      NO
                    │                       │
              Confirma OK          Muestra error con:
                                   • Producto
                                   • Cantidad solicitada
                                   • Cantidad disponible
                                   • Almacén evaluado
```

### Condiciones para que se valide

| Condición | Descripción |
|-----------|-------------|
| **Bloqueo activo** | En **Ventas > Configuración > Ajustes**, la opción **"Bloquear ventas sin stock"** debe estar activa. |
| **Producto almacenable** | Solo se validan productos con la casilla **"Almacenable"** marcada (campo `is_storable = True`). Productos de tipo consumible o servicio se ignoran. |
| **Cantidad > 0** | Las líneas con cantidad menor o igual a cero no generan bloqueo. |
| **Almacén incluido** | Si en configuración se definieron **"Validar solo ciertos almacenes"**, la orden debe pertenecer a uno de esos almacenes. Si no se define ninguno, se validan todos. |
| **Sin excepción de usuario** | Si la compañía permite excepciones por usuario, el usuario debe **NO** tener el grupo **"Permitir confirmar sin stock"**. |

### Mensaje de error mostrado

```
No hay stock suficiente para confirmar la orden:

Producto: [Nombre del producto]
Solicitado: [cantidad] [unidad de medida]
Disponible (sin reservas) en Almacén [Nombre]: [cantidad] [unidad de medida]
```

> **Nota:** Si una orden tiene **varios productos sin stock**, el mensaje lista todos los productos faltantes, no solo el primero.

---

## 2. ¿Se contempla la reserva?

**Sí, se contempla.** El módulo utiliza la cantidad **libre** (`free_qty`), es decir, el stock disponible **después de descontar las reservas existentes**.

### ¿Qué significa `free_qty`?

| Concepto | Definición |
|----------|------------|
| `qty_available` | Stock físico total en el almacén. |
| `reserved_quantity` | Stock ya reservado por otras órdenes de venta, movimientos o operaciones de inventario pendientes. |
| **`free_qty`** | **`qty_available - reserved_quantity`**. Es el stock realmente disponible para nuevas ventas. |

### Ejemplo práctico

```
Stock físico en Almacén Central:     100 unidades
Reservado por otras órdenes:         - 30 unidades
─────────────────────────────────────────────────
Free qty (disponible real):           70 unidades

Nueva orden solicita:                 80 unidades
─────────────────────────────────────────────────
Resultado: BLOQUEADO (70 < 80)
```

En este caso, aunque haya 100 unidades físicas, la orden se bloquea porque solo hay **70 libres** después de las reservas.

### ¿Dónde se ve en el código?

```python
# En models/sale_order.py
products = products.with_company(company).with_context(warehouse=self.warehouse_id.id)
available_by_product = {product.id: product.free_qty for product in products}
```

El campo `free_qty` es nativo de Odoo y ya tiene en cuenta:
- Reservas de otras órdenes de venta confirmadas.
- Movimientos de stock pendientes.
- La compañía y el almacén de la orden (`with_context(warehouse=...)`).

---

## 3. Configuración del módulo

### Activar el bloqueo

1. Ir a **Ventas > Configuración > Ajustes**.
2. En la sección **"Bloqueo por stock"**, activar **"Bloquear ventas sin stock"**.
3. *(Opcional)* Activar **"Permitir excepciones por usuario"** para dar flexibilidad a ciertos perfiles.
4. *(Opcional)* Seleccionar **"Validar solo ciertos almacenes"** si el bloqueo no aplica a todos los almacenes.

### Crear excepciones por usuario

1. Ir a **Configuración > Usuarios y Compañías > Usuarios**.
2. Editar el usuario deseado.
3. En la pestaña **"Acceso"**, activar el grupo **"Permitir confirmar sin stock"** (bajo la categoría **Ventas**).

> **Importante:** Este grupo solo tiene efecto si la compañía tiene activada la opción **"Permitir excepciones por usuario"**.

---

## 4. Botón "Reversar para editar"

El módulo agrega un botón **"Reversar para editar"** en la cabecera de la orden de venta, visible cuando:

- La orden está en estado **Confirmado** (`sale`) o en algún estado de aprobación.
- **No** tiene facturas activas (diferentes de canceladas).
- **No** tiene entregas (pickings) activas (diferentes de canceladas).

Esto permite corregir la orden si se bloqueó por stock y luego revertirla a *Cotización* para ajustar cantidades o productos.

---

## 5. Resumen técnico rápido

| Elemento | Valor / Comportamiento |
|----------|------------------------|
| **Campo de stock usado** | `product.free_qty` (cantidad libre, sin reservas) |
| **Productos validados** | Solo almacenables (`is_storable = True`) |
| **Cantidad comparada** | Suma de cantidades por producto en la orden, convertidas a la UoM base |
| **Contexto de stock** | `warehouse=self.warehouse_id.id`, `with_company(company)` |
| **Métodos que validan** | `_action_confirm`, `write` (si state='sale'), `_check_stock_on_state_sale` (constraint) |
| **Dependencias** | `sale`, `sale_stock`, `stock`, `sale_account_manager_customer_credit_limit_approval` |

---

## 6. Consideraciones importantes

1. **Las reservas de la propia orden no se descontarán doblemente:** si la orden ya está confirmada y se intenta modificar, el constraint `_check_stock_on_state_sale` valida nuevamente; esto es útil para evitar que ediciones manuales dejen una orden confirmada sin stock.

2. **Conversión de unidades de medida:** si una línea de venta usa una UoM diferente a la del producto, la cantidad se convierte antes de comparar (`product_uom._compute_quantity`).

3. **Agrupación por producto:** si una orden tiene el mismo producto en varias líneas, las cantidades se suman antes de comparar con el stock disponible.

4. **El campo `free_qty` depende de la fecha y estado de los movimientos:** asegúrese de que las reservas estén actualizadas (por ejemplo, que las órdenes canceladas hayan liberado su stock).
