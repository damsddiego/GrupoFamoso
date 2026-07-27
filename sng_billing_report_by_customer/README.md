# Reporte de Facturación por Cliente

Módulo para Odoo 18 que consolida facturas de cliente publicadas y notas de
crédito por cliente comercial y compañía.

## Uso

Abra **Contabilidad → Reportes → Facturación por Cliente** y seleccione:

- cantidad de meses (incluye el mes actual);
- una o varias compañías activas;
- un cliente, o deje el campo vacío para todos;
- un monto neto mínimo, o déjelo vacío para incluir todos.

El resultado se puede ver en pantalla, descargar en PDF o exportar a Excel.
Los importes se calculan en la moneda de cada compañía; las notas de crédito se
restan para obtener la facturación neta. Desde la vista en pantalla se puede
abrir el detalle de documentos de cada cliente.

Las acciones **Ver en pantalla**, **PDF** y **Excel** se muestran en la barra
superior del asistente para que estén disponibles en la vista de página completa.
