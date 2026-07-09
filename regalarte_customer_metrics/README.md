# Regalarte Customer Metrics

## Objetivo

`regalarte_customer_metrics` agrega indicadores comerciales y financieros en la ficha del cliente y crea una capa analitica por compania para consultar, filtrar, ordenar, agrupar y exportar esas metricas.

El modulo esta pensado para trabajar sobre:

- `res.partner`
- `account.move`
- `account.move.line`
- `account.partial.reconcile`

Su foco es mostrar informacion util para ventas, credito y cobranza usando el `commercial_partner_id` como cliente consolidado.

## Que resuelve

El modulo calcula y expone estas metricas:

- `DPP`: dias promedio de pago
- `Venta Mes Actual`
- `Promedio Trimestral`
- `Promedio Semestral`
- `Promedio Anual`
- `Promedio Cobranza Mensual`
- `Promedio Cobranza Trimestral`

Ademas:

- muestra estas metricas en la ficha del cliente para la compania activa
- mantiene un dashboard analitico por compania
- permite exportar a XLSX
- soporta cron de recarga
- evita mezclar resultados entre companias

## Arquitectura

El modulo trabaja en 2 niveles.

### 1. Capa operativa en `res.partner`

La ficha del cliente muestra la metrica correspondiente a:

- el `commercial_partner_id` del contacto
- la compania activa del usuario

Esto se resuelve con el campo computado:

- `customer_metric_current_id`

Desde esa relacion se muestran campos `related` en la vista del partner.

### 2. Capa analitica en `regalarte.customer.metric`

Este es el modelo principal de almacenamiento y analitica.

Guarda una fila por:

- cliente comercial
- compania

Campos principales:

- `partner_id`
- `company_id`
- `salesperson_partner_id`
- `currency_id`
- `country_id`
- metricas monetarias y DPP
- `customer_metrics_last_update`

El vendedor del dashboard se toma del vendedor de comisiones:

- primero `res.partner.assigned_salesperson_id`
- si no existe, el vendedor mas reciente en `account.move.salesperson_id`

Constraint importante:

- `unique(partner_id, company_id)`

Eso garantiza que cada cliente tenga una sola metrica por compania.

## Flujo de calculo

### Consolidacion del cliente

Todos los calculos usan `commercial_partner_id`.

Esto evita diferencias entre:

- empresa matriz
- contactos hijos
- direcciones de factura o entrega

### Ventas

Las ventas se calculan con `account.move`:

- `state = 'posted'`
- `move_type in ('out_invoice', 'out_refund')`
- `company_id = compania evaluada`

Se usa `amount_total_signed`.

Decision funcional:

- las notas de credito se restan automaticamente

Esto hace que los promedios representen venta neta.

### Cobranza

La cobranza no toma pagos solo por existir.

Solo considera montos efectivamente conciliados contra facturas de cliente, usando:

- `account.partial.reconcile.amount`
- `account.partial.reconcile.max_date`

La contraparte conciliada debe corresponder a un cobro real:

- `origin_payment_id IS NOT NULL`
- o `statement_line_id IS NOT NULL`
- o journal tipo `bank` o `cash`

Eso evita inflar cobranza con movimientos contables que no representan cobro real.

### DPP

El DPP se calcula solo sobre facturas:

- `out_invoice`
- `posted`
- `payment_state = 'paid'`

Criterio usado:

- si una factura se pago con varios cobros, se toma la ultima fecha de conciliacion real que termina de saldar la factura

En otras palabras:

- `DPP = promedio(fecha_ultimo_cobro_real - fecha_factura)`

Este criterio es estable y consistente para pagos parciales.

## Formulas

### Venta Mes Actual

- total neto facturado del mes calendario actual

### Promedio Trimestral

- total neto facturado ultimos 3 meses / 3

### Promedio Semestral

- total neto facturado ultimos 6 meses / 6

### Promedio Anual

- total neto facturado ultimos 12 meses / 12

### Promedio Cobranza Mensual

- total efectivamente cobrado ultimos 3 meses / 3

### Promedio Cobranza Trimestral

- total efectivamente cobrado ultimos 12 meses / 4

## Recalculo

### Recalculo manual desde partner

En la ficha del cliente hay un boton:

- `Actualizar Metricas`

Ese boton recalcula el cliente comercial para:

- todas las companias activas del contexto

### Recalculo programado

Existe un cron diario que recorre todas las companias y recalcula:

- todos los clientes relevantes

Clientes relevantes significa:

- partners con `customer_rank > 0`
- o partners que tengan facturas publicadas en la compania

### Recalculo masivo

Tambien hay accion de servidor desde lista para:

- recalcular metricas
- exportar XLSX

## Dashboard

El dashboard principal ya no vive sobre `res.partner`.

Vive sobre:

- `regalarte.customer.metric`

Eso permite:

- una fila por cliente y compania
- filtros correctos multi-compania
- agrupaciones por vendedor, compania y pais
- pivot y graph sin ambiguedad

Vistas disponibles:

- `list`
- `pivot`
- `graph`
- `form`

Menu:

- `Contacts / Dashboard Metricas`

## Exportacion XLSX

El modulo expone un flujo XLSX propio.

Se puede exportar desde:

- ficha del cliente
- seleccion en lista
- dashboard

El archivo exporta por compania:

- compania
- cliente
- vendedor
- DPP
- ventas
- promedios
- cobranzas
- fecha de ultima actualizacion

## Multi-compania

Este fue el cambio mas importante de la fase final.

Antes las metricas quedaban guardadas directamente en `res.partner`, lo cual podia mezclar resultados entre companias.

Ahora:

- el almacenamiento real esta en `regalarte.customer.metric`
- `res.partner` solo muestra la metrica de la compania activa

Resultado:

- dashboard correcto por compania
- exportacion correcta por compania
- ficha del cliente consistente con el contexto actual

## Archivos clave

### Modelos

- `models/customer_metric.py`
- `models/res_partner.py`

### Vistas

- `views/customer_metric_views.xml`
- `views/res_partner_views.xml`

### Cron y acciones

- `data/ir_cron.xml`
- `data/ir_actions_server.xml`

### Exportacion XLSX

- `controllers/main.py`
- `static/src/js/action_manager.js`

## Operacion diaria

### Para consultar metricas de un cliente

1. Abrir el partner.
2. Ir a la pestana `Indicadores del Cliente`.
3. Revisar los valores mostrados para la compania activa.

### Para recalcular un cliente especifico

1. Abrir el partner.
2. Click en `Actualizar Metricas`.

### Para analisis global

1. Ir a `Contacts / Dashboard Metricas`.
2. Usar filtros por:
   - DPP
   - compania
   - vendedor
   - pais
3. Cambiar entre lista, pivot y grafico.

### Para exportar

1. Desde partner o lista, usar `Exportar XLSX`.

## Consideraciones tecnicas

- Los calculos usan SQL batch para evitar ORM fila por fila.
- Se hace `flush` previo de modelos contables antes de consultar.
- La lectura de metricas en partner es liviana porque usa `Many2one` + `related`.
- El dashboard trabaja sobre un modelo persistido, no sobre calculo al vuelo.

## Limitaciones actuales

- No guarda historico mensual o snapshot por periodo.
- El cron recalcula estado actual, no series de tiempo.
- El XLSX exporta metricas actuales, no historicas.

## Mejora futura recomendada

La siguiente evolucion natural del modulo seria un historico mensual:

- `partner + company + period`

Eso permitiria:

- tendencia de DPP
- comparacion de ventas y cobranza por mes
- KPI historicos
- dashboard temporal real

## Resumen

El modulo queda dividido asi:

- `res.partner`: capa de consulta rapida por compania activa
- `regalarte.customer.metric`: capa analitica persistida por cliente y compania

Con esto el modulo es:

- usable en operacion diaria
- exportable
- analizable
- mantenible
- correcto para multi-compania
