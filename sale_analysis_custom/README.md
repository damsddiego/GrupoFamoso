# Sales Analysis Custom - Salesperson Integration

## Descripción

Este módulo extiende el **Análisis de Ventas** estándar de Odoo (`sale.report`) para integrar el sistema de vendedores del módulo **sales_commission_omax**.

### Cambio Principal

**Comportamiento Original:**
- El vendedor se obtiene del campo `user_id` en la orden de venta (`sale.order`)
- Este campo apunta a un usuario del sistema (`res.users`)

**Comportamiento Nuevo:**
- Se agrega un **nuevo campo** `salesperson_partner_id` en el análisis de ventas
- Este campo muestra directamente el contacto vendedor (`res.partner`)
- Proviene del campo `salesperson_id` de la orden de venta (módulo `sales_commission_omax`)
- Muestra el nombre del contacto con `is_salesperson = True`
- El campo `user_id` original se mantiene sin cambios

## Integración con sales_commission_omax

Este módulo depende de `sales_commission_omax`, que proporciona:

### Campos en res.partner:
- **`is_salesperson`**: Boolean que marca a un contacto como vendedor
- **`assigned_salesperson_id`**: Vendedor asignado por defecto a un cliente

### Campos en sale.order:
- **`salesperson_id`**: Many2one a `res.partner` con dominio `[('is_salesperson', '=', True)]`
- Se asigna automáticamente desde `partner.assigned_salesperson_id` al seleccionar cliente

## Funcionamiento Técnico

El módulo utiliza **herencia** del modelo `sale.report` y realiza lo siguiente:

### 1. Agrega un nuevo campo en el modelo:
```python
salesperson_partner_id = fields.Many2one(
    comodel_name='res.partner',
    string="Vendedor (Contacto)",
    readonly=True
)
```

### 2. `_select_sale()` - Agrega el campo al SELECT:
```sql
-- Se agrega al final del SELECT
s.salesperson_id AS salesperson_partner_id
```

### 3. `_group_by_sale()` - Agrega al GROUP BY:
```sql
-- Se añade al final del GROUP BY
s.salesperson_id
```

### 4. Vistas XML:
- **Lista**: Muestra el campo `salesperson_partner_id` después de `user_id`
- **Búsqueda**: Permite filtrar y agrupar por vendedor contacto
- **Pivot**: Campo disponible para análisis multidimensional

## Lógica de Negocio

1. En la orden de venta, el usuario selecciona un cliente
2. El campo `salesperson_id` se llena automáticamente con el vendedor asignado al cliente (`assigned_salesperson_id`)
3. Este vendedor aparece en el análisis de ventas en el campo **"Vendedor (Contacto)"**
4. Ahora puedes filtrar y agrupar por el contacto vendedor real, no por el usuario de Odoo
5. El campo `user_id` original (Salesperson) sigue disponible para compatibilidad

## Instalación

### Prerequisitos
Asegúrate de tener instalado el módulo **sales_commission_omax** primero.

### Pasos:
1. El módulo ya está en `odoo18-custom-addons/sale_analysis_custom`
2. Actualizar lista de aplicaciones en Odoo
3. Buscar "Sales Analysis Custom"
4. Instalar

## Uso

Una vez instalado, el módulo modifica automáticamente el reporte estándar **Análisis de Ventas** en:
- **Ventas > Reportes > Análisis de Ventas**

No hay vistas adicionales, ya que extiende el reporte existente.

### Flujo de Trabajo:

1. **Crear Vendedor**: Ir a Contactos y crear/editar un contacto, marcar ✓ `is_salesperson = True`
2. **Asignar a Cliente**: En el cliente, asignar el vendedor en `assigned_salesperson_id`
3. **Crear Orden**: Al crear una orden de venta, el campo `salesperson_id` se llena automáticamente
4. **Ver Análisis**:
   - Ir a Ventas > Reportes > Análisis de Ventas
   - Verás una nueva columna **"Vendedor (Contacto)"**
   - Puedes agrupar por este campo para análisis por vendedor
   - También disponible en búsquedas y tablas dinámicas

## Ventajas

✅ **Nuevo campo dedicado**: "Vendedor (Contacto)" muestra el vendedor real
✅ **Integración perfecta**: Usa el mismo vendedor del sistema de comisiones
✅ **Vendedores son contactos**: No necesitan ser usuarios de Odoo
✅ **Análisis preciso**: Agrupa y filtra por el vendedor asignado al cliente
✅ **Compatible**: No modifica campos existentes, solo agrega uno nuevo
✅ **Disponible en todas las vistas**: Lista, búsqueda, pivot y gráficos

## Estructura del Módulo

```
sale_analysis_custom/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── sale_report.py       # Herencia de sale.report
└── README.md
```

## Notas Importantes

- Este módulo NO crea un modelo nuevo, sino que extiende el existente
- Los cambios afectan a todos los análisis de ventas
- Es compatible con otros módulos que también extiendan `sale.report`

## Licencia

LGPL-3

## Autor

SNG
https://sngcloud.com
