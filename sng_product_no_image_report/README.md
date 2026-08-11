# Reporte de Artículos sin Imagen por Compañía

Lista los productos (plantillas) **activos** que no tienen imagen principal
(`image_1920`) cargada, con su código interno y descripción, agrupados por
compañía.

## Menús

Inventario → Informes:

- **Artículos sin Imagen** — abre el listado directo, agrupado por compañía.
- **Artículos sin Imagen (filtros)** — wizard para acotar por compañías,
  categoría, tipo y banderas de venta/compra antes de abrir el listado.

## Modelo

`sng.product.no.image` es una **SQL VIEW** de solo lectura (`_auto = False`),
por lo que no almacena datos ni requiere recálculos: siempre refleja el estado
actual de los productos.

Un producto aparece en el reporte cuando **no existe** un `ir.attachment` con
`res_field = 'image_1920'` y tamaño mayor a 0 apuntando a esa plantilla.

### Campos

| Campo | Descripción |
|---|---|
| `default_code` | Código interno |
| `product_name` | Descripción (es_CR, con respaldo a es_ES / en_US) |
| `barcode` | Código de barras de la primera variante activa que tenga |
| `categ_id`, `type`, `is_storable` | Clasificación del producto |
| `list_price` | Precio de venta |
| `sale_ok`, `purchase_ok` | Banderas de venta y compra |
| `extra_image_count` | Imágenes adicionales cargadas (pestaña Imágenes). Si es > 0, el producto tiene fotos pero ninguna como imagen principal |
| `create_date` | Fecha de creación |
| `company_id` | Compañía (vacío = producto compartido entre todas) |

## Multi-compañía

Una `ir.rule` global filtra por las compañías activas del usuario e incluye
siempre los productos compartidos (`company_id = False`).

## Exportar a Excel

Usar el botón estándar de exportación de Odoo desde la vista de lista
(seleccionar todo → ⚙ → Exportar). La vista *pivot* permite descargar el
conteo por compañía y categoría.

## Permisos

Lectura para `stock.group_stock_user` y `sales_team.group_sale_salesman`.
El botón de la fila abre la ficha del producto para cargarle la imagen.

## Instalación

```bash
sudo systemctl stop odoo18
/opt/odoo18/odoo18-venv/bin/python /opt/odoo18/odoo18/odoo-bin \
    -c /etc/odoo18.conf -d prod_gf -i sng_product_no_image_report \
    --stop-after-init --no-http
sudo systemctl start odoo18
```
