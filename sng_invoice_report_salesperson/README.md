# SNG Vendedor en Análisis de Facturas y tablero Facturación

Expone el vendedor real de la factura (`account.move.salesperson_id`, contacto
con `is_salesperson` definido por `sales_commission_omax`) donde Odoo muestra
por defecto el usuario (`invoice_user_id`):

- **Análisis de facturas** (`account.invoice.report`): columna «Vendedor
  (Contacto)» visible por defecto, campo de búsqueda y agrupación en lista,
  gráfica y pivote.
- **Tableros > Facturación** (`spreadsheet_dashboard_account`): el filtro
  «Vendedor» elige contactos vendedores y la tabla «Top vendedores» agrupa por
  ese contacto. La gráfica, al hacer clic en un punto, abre la lista anterior
  con la columna nueva.

## Tablero

`data/files/invoicing_dashboard.json` **no se edita a mano**. Se genera con:

```bash
python3 tools/generar_tablero.py
```

a partir del JSON original de Odoo Enterprise. El registro
`spreadsheet_dashboard_account.dashboard_invoicing` se sobreescribe en
`data/spreadsheet_dashboard.xml`; como este módulo depende de
`spreadsheet_dashboard_account`, su versión prevalece en cada `-u`. Si alguien
edita el tablero desde la interfaz, esa edición se pierde al actualizar este
módulo.

## Pruebas

```bash
./odoo18-venv/bin/python3 ./odoo18/odoo-bin -c <conf de prueba> -d <bd de prueba> \
  -u sng_invoice_report_salesperson --test-enable \
  --test-tags /sng_invoice_report_salesperson --workers=0 --no-http \
  --http-port=8099 --stop-after-init
```
