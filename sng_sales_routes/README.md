# SNG Rutas / Territorios de Venta

## Objetivo

El módulo **SNG Rutas / Territorios de Venta** permite clasificar clientes y documentos comerciales por una ruta o territorio comercial.

La ruta funciona como un dato de clasificación y reporte. No cambia el vendedor asignado al cliente, no asigna vendedores automáticamente y no modifica las reglas de comisión.

## Dónde se configura

El catálogo de rutas está disponible en:

**Contactos > Rutas / Territorios**

Desde este menú se pueden crear y administrar las rutas disponibles para clientes y documentos.

Cada ruta tiene los siguientes datos:

- **Nombre**: nombre visible de la ruta o territorio.
- **Código**: identificador corto opcional.
- **Vendedor de referencia**: vendedor relacionado solo como dato informativo.
- **Compañía**: compañía a la que pertenece la ruta. Si se deja vacía, queda disponible de forma global.
- **Activo**: permite archivar rutas que ya no se usan.
- **Notas**: información adicional.

## Uso en clientes

En la ficha del cliente, dentro de la sección de ventas, aparece el campo:

**Ruta/Territorio**

Al asignar una ruta al cliente, esta queda disponible para reportes y se copiará automáticamente a los documentos comerciales nuevos que se creen para ese cliente.

Cambiar la ruta del cliente afecta únicamente documentos nuevos. Los documentos ya creados conservan la ruta histórica que tenían.

## Uso en pedidos de venta

Cuando se crea un pedido de venta para un cliente con ruta asignada, el pedido copia esa ruta automáticamente.

El campo **Ruta/Territorio** en el pedido queda editable, por si se necesita corregir o ajustar la ruta para una venta específica.

La ruta del pedido se conserva como dato histórico.

## Uso en facturas

Cuando una factura se crea desde un pedido de venta, la factura conserva la ruta del pedido.

Si la factura se crea manualmente desde el cliente, la factura toma la ruta actual del cliente.

La ruta en facturas permite filtrar y agrupar documentos por territorio sin depender de cambios futuros en el cliente.

## Uso en pagos

En pagos de cliente, el sistema intenta identificar la ruta desde las facturas conciliadas.

Si el pago no tiene facturas conciliadas, usa la ruta actual del cliente como referencia.

Si el pago está asociado a facturas de distintas rutas, se usa la ruta del cliente como criterio principal; si no existe, se toma una de las rutas de las facturas.

## Uso en análisis de comisiones

El módulo agrega **Ruta/Territorio** al análisis de comisiones.

La ruta se copia desde la orden de venta o factura que originó la línea de comisión. Si no existe orden ni factura, se toma desde el cliente relacionado.

Este dato permite filtrar y agrupar comisiones por ruta, pero no cambia el cálculo de comisiones.

## Filtros y agrupaciones

El campo **Ruta/Territorio** se puede usar para buscar o agrupar en:

- Contactos / clientes.
- Pedidos de venta.
- Facturas de cliente.
- Pagos de cliente.
- Análisis de comisiones.

Esto permite responder preguntas como:

- Qué clientes pertenecen a una ruta.
- Cuánto se vendió por ruta.
- Qué facturas corresponden a cada territorio.
- Qué pagos están asociados a una ruta.
- Cuánta comisión se generó por territorio.

## Reporte de clientes por ruta

El módulo agrega el reporte:

**Contactos > Reporte Clientes por Ruta**

Este reporte muestra una línea por cliente activo e incluye:

- **Unique ID**: código único del cliente.
- **Nombre**: nombre del cliente.
- **Código de ruta**: código configurado en la ruta.
- **Ruta (Nombre)**: nombre de la ruta o territorio.
- **Nombre vendedor**: vendedor asignado al cliente para comisiones.
- **Teléfono**: teléfono del cliente.
- **Términos de pago**: condición de pago del cliente.
- **Lista de precio**: lista de precio configurada en el cliente, si existe.
- **Fecha última factura**: última factura de cliente publicada.
- **Dirección**: dirección principal del cliente.

El reporte es de solo lectura y puede exportarse desde la vista de lista de Odoo.

También permite filtrar clientes con ruta, sin ruta, con factura o sin factura. La vista permite agrupar por ruta, vendedor y compañía.

## Columnas en cuenta por cobrar vencida

El módulo también extiende el reporte nativo de Odoo:

**Contabilidad > Reportes > Reportes de socios > Cuenta por cobrar vencida**

Se agregan tres columnas al inicio del reporte:

- **Código cliente**: toma el `unique_id` del cliente.
- **Ruta**: muestra la ruta o territorio asignado al cliente.
- **Vendedor**: muestra el vendedor asignado al cliente para comisiones.

Estas columnas aparecen tanto en las líneas agrupadas por cliente como en las líneas desplegadas de apuntes/facturas. Son informativas y no modifican los saldos ni los vencimientos del reporte.

## Comportamiento histórico

El módulo guarda la ruta como una copia histórica en pedidos, facturas y pagos.

Ejemplo:

1. El cliente tiene asignada la ruta **San José Centro**.
2. Se crea un pedido de venta.
3. El pedido guarda **San José Centro**.
4. Luego el cliente cambia a la ruta **Heredia**.
5. El pedido anterior sigue mostrando **San José Centro**.
6. Los documentos nuevos usarán **Heredia**.

Este comportamiento ayuda a mantener reportes históricos correctos.

## Permisos

Los usuarios internos pueden ver las rutas.

Los gerentes de ventas y gerentes de comisiones pueden crear, editar y eliminar rutas.

## Consideraciones importantes

- La ruta no reemplaza al vendedor.
- La ruta no modifica `Vendedor asignado`.
- La ruta no cambia reglas ni porcentajes de comisión.
- La ruta es principalmente un dato para clasificación, control y reportes.
- No se cargan rutas iniciales automáticamente; deben crearse manualmente o mediante una importación posterior.
