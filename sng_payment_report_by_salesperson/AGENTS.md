<!-- AGENTS.md - Guía para agentes de IA del módulo sng_payment_report_by_salesperson -->

# sng_payment_report_by_salesperson — Guía del Módulo

> **⚠️ INSTRUCCIÓN OBLIGATORIA PARA IAs:**  
> Cada vez que se modifique cualquier archivo, funcionalidad, estructura, dependencia, campo, vista, regla de seguridad o comportamiento de este módulo, **DEBES actualizar este archivo `AGENTS.md`** para mantener la documentación sincronizada con el código.  
> Si eliminas, renombras o agregas archivos, actualiza la sección **Estructura de Archivos**.  
> Si cambias la lógica de la vista SQL, los campos, los filtros o las reglas de acceso, actualiza las secciones correspondientes.  
> **No finalices una tarea sobre este módulo sin verificar que esta guía refleje el estado actual del código.**

---

## 1. Propósito del Módulo

Módulo de Odoo 18 (Community / Enterprise) que genera un **reporte de pagos de clientes** con información detallada de las facturas aplicadas, el vendedor asignado al cliente y el tiempo transcurrido entre la emisión de la factura y su cobro.

Ubicación del menú en Odoo:  
**Contabilidad → Reportes → Reporte de Pagos**

---

## 2. Información General del Módulo

| Atributo | Valor |
|----------|-------|
| Nombre técnico | `sng_payment_report_by_salesperson` |
| Nombre visible | `Payment Report` |
| Versión | `18.0.2.3.0` |
| Categoría | `Accounting/Accounting` |
| Autor | `SNG` |
| Licencia | `LGPL-3` |
| Instalable | `True` |
| Aplicación | `False` |
| Auto-instalable | `False` |
| Dependencias | `account` |

---

## 3. Estructura de Archivos

```
/opt/odoo18/odoo18-custom-addons/sng_payment_report_by_salesperson/
├── __init__.py                          # Importa el paquete models
├── __manifest__.py                      # Metadatos del módulo y lista de archivos data
├── AGENTS.md                            # Este archivo (guía para IAs)
├── README.md                            # Documentación breve para humanos
├── models/
│   ├── __init__.py                      # Importa payment_report_salesperson
│   └── payment_report_salesperson.py    # Modelo SQL y lógica del reporte
├── report/                              # (Reservado; vacío actualmente)
├── security/
│   ├── ir.model.access.csv              # Permisos de lectura por grupo contable
│   └── security.xml                     # Regla de multi-compañía
├── static/
│   └── description/
│       └── index.html                   # Descripción visual del módulo para Apps
└── views/
    └── payment_report_salesperson_views.xml  # Vistas list/pivot/graph/search, acción y menú
```

### Descripción de archivos clave

| Archivo | Responsabilidad |
|---------|-----------------|
| `__manifest__.py` | Define dependencias, datos a cargar y metadatos del módulo. |
| `models/payment_report_salesperson.py` | Modelo `_auto = False` que crea una **vista SQL** (`payment_report_salesperson`) y personaliza `read_group` para totales correctos. |
| `security/ir.model.access.csv` | Acceso de solo lectura para grupos contables (`group_account_user`, `group_account_manager`, `group_account_readonly`). |
| `security/security.xml` | Regla `ir.rule` que filtra registros por las compañías activas del usuario (`company_id in company_ids`). |
| `views/payment_report_salesperson_views.xml` | Define vistas lista, pivot, gráfico, búsqueda, acción de ventana y elemento de menú. |
| `static/description/index.html` | Tarjeta informativa que aparece en la página de Apps dentro de Odoo. |
| `README.md` | Documentación de alto nivel en español. |
| `AGENTS.md` | Esta guía. |

---

## 4. Modelo: `payment.report.salesperson`

### Características

- Tipo: `models.Model`
- `_name = 'payment.report.salesperson'`
- `_description = 'Reporte de Pagos'`
- `_auto = False` → la tabla/vista se crea manualmente en `init()`.
- `_order = 'payment_date desc'`
- Vista SQL subyacente: `payment_report_salesperson`

### Campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `partner_id` | `Many2one('res.partner')` | Cliente que realizó el pago. |
| `partner_name` | `Char` | Nombre del cliente. |
| `salesperson_id` | `Many2one('res.partner')` | Vendedor asignado al cliente (por compañía del pago). |
| `salesperson_name` | `Char` | Nombre del vendedor. |
| `payment_id` | `Many2one('account.payment')` | Pago de cliente. |
| `payment_date` | `Date` | Fecha del pago. |
| `payment_amount` | `Monetary` | Monto del pago (o monto de la reconciliación parcial). |
| `payment_reference` | `Char` | Referencia / nombre del pago. |
| `invoice_id` | `Many2one('account.move')` | Factura vinculada al pago. |
| `invoice_name` | `Char` | Número de factura. |
| `invoice_date` | `Date` | Fecha de emisión de la factura. |
| `invoice_amount_untaxed` | `Monetary` | Monto sin impuestos de la factura. |
| `invoice_untaxed_pending` | `Monetary` | Saldo pendiente sin impuestos **antes** de aplicar este pago. |
| `invoice_untaxed_balance` | `Monetary` | Saldo sin impuestos **después** de aplicar este pago. |
| `days_to_pay` | `Integer` | Días entre `invoice_date` y `payment_date`. |
| `is_reconciled` | `Boolean` | `True` si el pago está reconciliado con una factura. |
| `payment_state` | `Selection` | Estado del pago: `draft`, `in_process`, `paid`, `canceled`, `rejected`. |
| `currency_id` | `Many2one('res.currency')` | Moneda del pago. |
| `company_id` | `Many2one('res.company')` | Compañía del pago (para multi-compañía). |

### Lógica de la vista SQL (`init()`)

La vista SQL se compone de dos consultas unidas con `UNION ALL`:

1. **Pagos reconciliados con facturas**
   - Incluye pagos `inbound` que tienen al menos una reconciliación parcial (`account.partial.reconcile`) con líneas de facturas de cliente (`out_invoice`, `out_refund`) en estado `posted`.
   - Calcula saldos decrecientes usando funciones de ventana (`SUM(...) OVER (PARTITION BY am.id ORDER BY ...)`).
   - Relaciona el vendedor leyendo el campo `rp.assigned_salesperson_id->>(ap.company_id::text)` como JSONB/JSON (clave por compañía).

2. **Pagos no reconciliados**
   - Incluye pagos `inbound` que **no** tienen reconciliaciones.
   - Campos de factura van en `NULL`.
   - Los `id` se desplazan `+ 1000000` para evitar colisiones con la primera consulta.

### Método `read_group()`

- Sobrescrito para corregir el total del campo `payment_amount` cuando se agrupa.
- Recalcula `payment_amount` sumando directamente los registros del dominio del grupo, evitando duplicados por agrupación.

### Dependencia implícita importante

El modelo asume que **`res.partner` dispone del campo `assigned_salesperson_id`** (aparentemente un campo JSON/JSONB indexado por ID de compañía). Si ese campo no existe o cambia de nombre/tipo, este módulo fallará al crear la vista SQL.

---

## 5. Vistas y Menú

Archivo: `views/payment_report_salesperson_views.xml`

### Vistas definidas

| ID externo | Tipo | Descripción |
|------------|------|-------------|
| `view_payment_report_salesperson_list` | `list` | Vista lista detallada con totales, colores de estado y campos opcionales. |
| `view_payment_report_salesperson_pivot` | `pivot` | Análisis por vendedor, cliente y mes. |
| `view_payment_report_salesperson_graph` | `graph` | Gráfico de montos por vendedor. |
| `view_payment_report_salesperson_search` | `search` | Búsqueda, filtros predefinidos y agrupaciones. |

### Acción y menú

| ID externo | Tipo | Descripción |
|------------|------|-------------|
| `action_payment_report_salesperson` | `ir.actions.act_window` | Abre el modelo en modo `list,pivot,graph`. |
| `menu_payment_report_salesperson_root` | `menuitem` | Inserta el menú bajo `account.menu_finance_reports` con secuencia `50`. |

### Filtros predefinidos disponibles

- Este Mes
- Mes Anterior
- Este Año
- Pago Rápido (≤ 30 días)
- Pago Normal (31-60 días)
- Pago Lento (> 60 días)
- Borrador / En Proceso / Pagado / Cancelado/Rechazado
- Reconciliados / No Reconciliados
- Fecha de Pago / Fecha de Factura

### Agrupaciones disponibles

- Vendedor
- Cliente
- Estado de Pago
- Fecha de Pago
- Mes de Pago
- Estado de Reconciliación
- Compañía

---

## 6. Seguridad

### Permisos (`security/ir.model.access.csv`)

| Grupo | Lectura | Escritura | Creación | Eliminación |
|-------|---------|-----------|----------|-------------|
| `account.group_account_user` | ✅ | ❌ | ❌ | ❌ |
| `account.group_account_manager` | ✅ | ❌ | ❌ | ❌ |
| `account.group_account_readonly` | ✅ | ❌ | ❌ | ❌ |

> El modelo es de **solo lectura**; no admite creación, edición ni eliminación desde la UI.

### Regla de registro (`security/security.xml`)

- Regla: `payment_report_salesperson_company_rule`
- Dominio: `[('company_id', 'in', company_ids)]`
- Propósito: filtrar los registros del reporte según las compañías activas del usuario en sesión.

---

## 7. Convenciones y Notas para IAs

- El modelo es una **vista SQL de solo lectura**. No agregues métodos `create`, `write` o `unlink` sin una razón muy clara.
- Cualquier cambio en la vista SQL debe probarse con datos reales o de prueba para evitar duplicados o pérdida de pagos.
- Si se agregan nuevos campos, recuerda:
  - Declararlos en el modelo Python.
  - Incluirlos en la consulta SQL.
  - Agregarlos a las vistas `list`, `pivot`, `graph` o `search` según corresponda.
- Respeta el orden de carga del manifiesto: primero seguridad, luego vistas.
- No uses `'tree'` en `view_mode`; en Odoo 18 se usa `'list'`.
- Mantén la licencia `LGPL-3` salvo que el usuario indique lo contrario.

---

## 8. Cómo Actualizar este Módulo

```bash
# Detener Odoo (recomendado)
sudo systemctl stop odoo18

# Actualizar el módulo
/opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -u sng_payment_report_by_salesperson \
  -d nombre_base_de_datos \
  --stop-after-init

# Reiniciar Odoo
sudo systemctl start odoo18
```

Recuerda limpiar caché si los cambios no se reflejan:

```bash
find /opt/odoo18/odoo18-custom-addons/sng_payment_report_by_salesperson \
  -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /opt/odoo18/odoo18-custom-addons/sng_payment_report_by_salesperson \
  -name "*.pyc" -delete
```

---

## 9. Historial de Cambios Sugerido

> **Nota para IAs:** Al modificar el módulo, añade una entrada breve aquí indicando la fecha, la versión y el cambio realizado.

| Fecha | Versión | Cambio |
|-------|---------|--------|
| 2026-07-07 | 18.0.2.3.0 | Creación inicial de `AGENTS.md` con la estructura completa del módulo. |

---

*Última actualización: 2026-07-07*
