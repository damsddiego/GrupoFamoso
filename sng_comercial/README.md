# Comercial (`sng_comercial`)

App propia para los reportes comerciales de SNG. Todo reporte comercial nuevo vive aquí, no en Ventas, Compras ni en otro módulo.

## Reporte Sell in / Sell out

| Concepto | Qué mide | Fecha |
|---|---|---|
| **Sell in** | Cantidad recibida de órdenes de compra, menos devoluciones a proveedor | Recepción (hora de Costa Rica) |
| **Sell out** | Cantidad facturada ligada a órdenes de venta, menos notas de crédito | Fecha de la factura |
| **Litros** | Unidades × litros por unidad del valor de volumen | — |

Entran los productos con valor en el atributo marcado como **pilar**. Al asignarle pilar a un producto, entra solo.

Menús:
- **Reportes › Sell in / Sell out**: pivot, gráfico y lista (`sng.comercial.sell.report`).
- **Reportes › Inventario comercial**: stock, tránsito (órdenes de compra confirmadas sin recibir) y bodega del grupo, al momento de la consulta (`sng.comercial.inventario.report`).
- **Reportes › Descargar Excel**: asistente con periodo y compañías; genera el libro con marca (hojas BASE DATOS, POR MES, TABLA y Notas).

## Configuración

1. **Atributos comerciales**: marca cuál atributo es pilar, base y volumen (uno por uso). Al instalar, el módulo marca los atributos llamados PILAR, BASE y VOLUMEN si no hay ambigüedad.
2. **Litros por volumen**: litros por unidad de cada valor del atributo de volumen. El módulo propone el número a partir del nombre («400ml» → 0.4, «ESTAÑÓN» → 208); revisa los que queden en 0.
3. **Ajustes › Bodega del grupo**: por compañía, cuál otra compañía le guarda inventario (para SAASA es GF). La columna «Bodega grupo» suma el stock de esa compañía con la misma referencia interna.
4. **Usuarios**: agrega a cada persona al grupo *Comercial / Usuario* (reportes) o *Comercial / Administrador* (además configura). Nadie los recibe por herencia.

Los reportes respetan las compañías activas del usuario y no requieren permisos de Compras ni de Inventario.

## Cómo agregar un reporte

Cada reporte es un conjunto de archivos con el mismo nombre base:

- `models/<reporte>.py`: modelo de análisis (`_auto = False` con `_table_query`) con `company_id`.
- `views/<reporte>_views.xml`: vistas y acción.
- `report/<reporte>_xlsx.py` (opcional): Excel como función pura `generar(datos) -> bytes`, sin Odoo, para poder probarlo solo.
- `tests/test_<reporte>.py`.
- Una entrada en `views/menus.xml` bajo **Reportes**, una fila en `security/ir.model.access.csv` y su regla multi-compañía en `security/sng_comercial_security.xml`.

La clasificación comercial ya está en la plantilla del producto (`sng_pilar_id`, `sng_base_id`, `sng_volumen_id`, `sng_litros_unidad`, almacenados): un reporte nuevo solo hace `JOIN product_template`.

## Pruebas

Nunca sobre `prod_gf`. El módulo solo depende de Odoo Community, así que las pruebas corren completas en una base vacía y desechable (unos 3 minutos; fuera de horario de ventas o con `nice`):

```bash
mkdir -p /tmp/addons_comercial && ln -sfn /opt/odoo18/odoo18-custom-addons/sng_comercial /tmp/addons_comercial/
createdb -O odoo18 -E UTF8 -T template0 --lc-collate=C --lc-ctype=C test_sng_comercial
nice -n 19 ionice -c3 ./odoo18-venv/bin/python3 ./odoo18/odoo-bin -d test_sng_comercial \
  --addons-path=/opt/odoo18/odoo18/addons,/tmp/addons_comercial --data-dir=/tmp/data_comercial \
  -i sng_comercial --without-demo=all --test-enable --test-tags /sng_comercial \
  --workers=0 --max-cron-threads=0 --no-http --http-port=8099 --stop-after-init
dropdb test_sng_comercial
```

En una copia de producción también corren (reutilizan los atributos ya marcados), siempre que la copia esté al día con el código: las pruebas de sell out publican facturas.
