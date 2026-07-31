# SNG Dashboard Gerencial

Dashboard para la toma de decisiones del grupo (GRUPO FAMOSO, PROTIRE, SAASA)
con indicadores en vivo y análisis IA con recomendaciones.

Menú: **Dashboard Gerencial**, visible SOLO para usuarios con uno de los
dos grupos de la sección "SNG Dashboard Gerencial" (Ajustes → Usuarios →
pestaña Permisos de acceso):

- **Acceso completo (ventas + inventario)** — ve todo el dashboard.
- **Solo Inventario** — ve únicamente la pestaña Inventario con su
  análisis IA. El servidor no le entrega datos de ventas, cobros, cartera
  ni la tabla por compañía (no es solo ocultarlos en pantalla), y en el
  historial de análisis solo ve los de tipo inventario (regla de registro).
- **Estrategia (compras y ventas)** — ve únicamente la pestaña Estrategia
  y su análisis IA (mismo mecanismo de filtrado en servidor y regla de
  registro). El grupo de acceso completo la ve automáticamente.
- **CXC - Pagos** — ve únicamente la pestaña CXC - Pagos (ventas vs
  cobros por compañía y resumen por vendedor) y su análisis IA (mismo
  mecanismo de filtrado en servidor y regla de registro). El grupo de
  acceso completo la ve automáticamente.

El botón **Actualizar análisis IA** (consume API y es global) solo
aparece y funciona para administradores con **Administración / Ajustes**
(`base.group_system`); el resto solo ve los análisis ya generados.

Ningún otro grupo lo implica: ni los administradores de Contabilidad lo
ven si no están en un grupo. El permiso se valida también en el servidor.
Respeta el selector de compañías nativo: los números corresponden a las
compañías activas del usuario.

## Qué muestra

- **KPIs**: ventas del mes (con variación vs el mismo corte del mes
  anterior), cobros del mes, cartera vencida (y % sobre el total),
  inventario valorado, DSO (días de cobro) y facturas abiertas.
- **Gráficas**: ventas vs cobros por mes (6/12/24 meses), cartera por
  antigüedad, top 10 clientes con deuda vencida, ventas por vendedor del mes
  (vendedor = contacto de `sales_commission_omax`), inventario por categoría.
- **Inventario a fondo** (ventana fija de 90 días de ventas/salidas):
  rotación anualizada y cobertura en meses, % de devoluciones (notas de
  crédito vs facturas), valor y conteo de productos **sin movimiento**
  (+180 días sin salidas), **sobrestock** (cobertura > 12 meses; se reporta
  el valor del exceso), rotación por categoría, top productos vendidos,
  más devueltos, mayor valor estancado y mayor sobrestock.
- **Estrategia** (pestaña, ventana de 90 días): compras del mes y ratio
  compras/ventas, margen bruto (COGS solo de entregas a cliente netas de
  devoluciones), **sugerido de compras** (demanda = unidades facturadas
  netas; cobertura objetivo configurable con el parámetro
  `sng_dashboard_gerencial.cobertura_objetivo_meses`, default 3),
  **quiebres de stock** con venta en riesgo, **ABC de Pareto** real
  (A ≤80% / B ≤95% / C resto + "Sin venta") con el inventario invertido
  por clase, margen por categoría, compras vs ventas por mes y compras
  por proveedor. Análisis IA propio (tipo estrategia).
- **CXC - Pagos** (pestaña, grupo propio o acceso completo): por cada
  compañía activa, gráfica de ventas vs cobros por mes (respeta el
  selector de período) y **resumen por vendedor** con columnas Vendedor,
  Monto sin IVA, Total con IVA y Monto del pago. Las ventas salen de las
  facturas (vendedor de `sales_commission_omax`) y los cobros de la vista
  del módulo `sng_payment_report_by_salesperson` (pago asignado al
  vendedor del cliente en la compañía del pago, montos en la moneda del
  pago). Análisis IA propio (tipo cxc) con foco en la brecha
  venta-cobro por vendedor.
- **Detalle por compañía** cuando hay más de una activa.
- **Análisis IA**: salud del negocio (buena/regular/crítica), resumen
  ejecutivo, alertas y recomendaciones priorizadas por área
  (ventas/cobranza/inventario/finanzas).

## Análisis IA

- Se genera **automáticamente cada lunes 06:00** (cron, una llamada por
  compañía) y **a demanda** con el botón *Actualizar análisis IA*.
- El botón genera los análisis **de uno en uno** (un request por
  compañía × tipo, con barra de progreso en el propio botón). No debe
  volver a hacerse en un solo request: cada llamada IA tarda 10-40 s y
  el total (16 análisis con 4 compañías) excede `limit_time_real` del
  worker (120 s), que mata el proceso y revierte todo sin error visible.
- El historial completo queda en *Dashboard Gerencial → Historial de
  análisis IA* (modelo `sng.dashboard.analisis`).
- Reutiliza la API key de Anthropic ya configurada en
  `sng_ruteros_pagos.anthropic_api_key` (respaldo:
  `sng_dashboard_gerencial.anthropic_api_key`). Modelo por defecto:
  `claude-opus-4-8`.
- Costo estimado: ~4 llamadas/semana por compañía (general, cxc,
  inventario, estrategia) + usos manuales → centavos de dólar al mes.

## Fuentes de datos

| Indicador | Fuente |
|---|---|
| Ventas | `account.move` (facturas − notas de crédito, publicadas, sin impuestos) |
| Cobros | `account.payment` entrantes de clientes en estado en proceso/pagado |
| Cartera | facturas de cliente publicadas con saldo pendiente |
| Inventario | `stock.valuation_layer`, suma de `value` (igual al reporte nativo de valoración; con costeo estándar `remaining_value` queda desfasado y no debe usarse) |
| Vendedor | `salesperson_id` de la factura (`sales_commission_omax`) |
| Cobros por vendedor (CXC - Pagos) | vista `payment_report_salesperson` de `sng_payment_report_by_salesperson` |

Todo se consulta en SQL directo filtrado por compañía; no se guarda ningún
dato agregado (solo los análisis IA).
