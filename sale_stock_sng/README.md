# Sale Stock CR (`sale_stock_sng`)

**Versión:** 18.0.1.0.3  
**Autor:** SNG Cloud — [sngcloud.com](https://sngcloud.com)  
**Licencia:** LGPL-3  
**Categoría:** Ventas / Inventario

---

## Descripción General

`sale_stock_sng` es un módulo de extensión para Odoo 18 que amplía el flujo estándar de **Ventas + Inventario** para soportar operaciones de **consignación a clientes** (bodegas en consignación). 

Sus funciones principales son:

1. **Ubicación de salida por cliente / por orden de venta** — Permite seleccionar en cada orden de venta la bodega interna desde la que se despacha la mercancía (útil para consignaciones donde el stock ya está en la ubicación del cliente).
2. **Propagación automática de la ubicación** — La ubicación seleccionada se propaga desde la orden → línea de orden → regla de aprovisionamiento → movimiento de stock, asegurando que el inventario se tome del lugar correcto.
3. **Destino correcto en devoluciones de entregas** — Cuando se devuelve una orden de entrega, la ubicación destino de la devolución queda por defecto como la ubicación origen de la entrega original.
4. **Filtro "Mi Bodega" en quants de inventario** — Cada usuario puede filtrar el inventario disponible mostrando solo los quants de su bodega asignada.
5. **Reporte XLSX de Consignaciones y CxC** — Genera un reporte Excel con el stock valorado en bodega del cliente y el saldo de cuentas por cobrar, con totales en Colones y Dólares.

---

## Módulos Requeridos

| Módulo | Descripción |
|---|---|
| `account` | Gestión contable (facturas, notas de crédito) |
| `sale_stock` | Integración ventas + inventario estándar de Odoo |
| `report_xlsx` | Motor de reportes Excel (OCA) |
| `partner_client_code` | Código de cliente en el contacto |
| `cr_electronic_invoice` | Facturación electrónica Costa Rica |

---

## Componentes Principales

### Modelos extendidos

| Modelo | Extensión introducida |
|---|---|
| `res.partner` | Campo `sale_location_id` (bodega asignada) y `team_id` (equipo de ventas) |
| `sale.order` | Campo `partner_sale_location_id` para forzar origen de despacho |
| `sale.order.line` | Propagación de `partner_sale_location_id` al aprovisionamiento |
| `stock.move` | Campo `partner_sale_location_id`; fuerza `make_to_stock` en movimientos de consignación |
| `stock.rule` | Sobreescribe la ubicación de origen del movimiento si proviene de consignación |
| `procurement.group` | Log de trazabilidad para productos/ubicaciones de traslado |
| `stock.picking` | Autocompletado de ubicaciones origen/destino al seleccionar el cliente en transferencias internas |
| `stock.return.picking` | En devoluciones de entregas, define como destino la ubicación origen del picking original |
| `stock.return.picking.line` | En devoluciones de entregas, define como destino de cada línea la ubicación origen del movimiento original |
| `stock.quant` | Campo calculado `in_my_location` para filtrar el inventario por bodega del usuario |
| `product.template` | Al cambiar tipo a `consu`, marca automáticamente `is_storable = True` |

### Wizards

| Wizard | Descripción |
|---|---|
| `consign.cxc.wizard` | Formulario de parámetros para el reporte (rango de fechas, vendedor, bodegas) |
| `report.sale_stock_sng.consign_cxc_xlsx` | Generador del archivo Excel con stock valorado y CxC por cliente |

### Vistas

| Archivo | Descripción |
|---|---|
| `res_partner_views.xml` | Agrega `sale_location_id` y `team_id` al formulario del contacto |
| `sale_order_views.xml` | Agrega `partner_sale_location_id` al formulario de orden de venta |
| `stock_quant_views.xml` | Agrega filtro **"Mi bodega"** a la búsqueda de inventario |

### Menús

El reporte de **Consignaciones y CxC** se encuentra en:  
`Ventas → Informes → Reportes Personalizados → Consignaciones y CxC`

---

## Instalación

```bash
# Instalar el módulo (reemplazar RegalarteProd por el nombre de tu base de datos)
python odoo18/odoo-bin -c /etc/odoo18.conf \
    -i sale_stock_sng \
    -d RegalarteProd \
    --stop-after-init
```

Para actualizarlo después de cambios:

```bash
python odoo18/odoo-bin -c /etc/odoo18.conf \
    -u sale_stock_sng \
    -d RegalarteProd \
    --stop-after-init
```

---

## Estructura del Módulo

```
sale_stock_sng/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── product.py            # Auto-marcado is_storable
│   ├── res_partner.py        # sale_location_id, team_id
│   ├── sale_order.py         # partner_sale_location_id
│   ├── stock_move.py         # Propagación ubicación consignación
│   ├── stock_picking.py      # Auto-ubicaciones en transferencias internas
│   ├── stock_quant.py        # Filtro "Mi bodega"
│   ├── stock_return_picking.py # Destino de devoluciones a ubicación origen
│   └── stock_rule.py         # Sobrescritura de location_id en reglas
├── views/
│   ├── res_partner_views.xml
│   ├── sale_order_views.xml
│   └── stock_quant_views.xml
├── wizards/
│   ├── __init__.py
│   ├── consign_cxc_wizard.py          # Modelo del wizard
│   ├── consign_cxc_wizard_views.xml   # Vista del wizard
│   ├── consign_cxc_xlsx.py            # Generador Excel
│   └── reports.xml                    # Declaración de la acción de reporte
└── security/
    └── ir.model.access.csv
```

---

## Seguridad (Permisos)

| Regla de acceso | Grupo | R | W | C | D |
|---|---|---|---|---|---|
| `access_consign_cxc_wizard_user` | Usuario interno | ✓ | ✓ | ✓ | ✗ |
| `access_consign_cxc_wizard_admin` | Administrador | ✓ | ✓ | ✓ | ✓ |

---

## Notas

- El módulo **no** crea menús de aplicación propios (`"application": False`).
- Las devoluciones de entregas (`outgoing`) vuelven por defecto a la ubicación desde donde salió la entrega.
- El campo `partner_sale_location_id` en la orden de venta es de solo lectura una vez que la orden pasa del estado Borrador/Enviada.
