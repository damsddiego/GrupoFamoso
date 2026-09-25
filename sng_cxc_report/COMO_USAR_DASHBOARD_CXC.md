# Como usar el Dashboard CxC Gerencial

Modulo: `sng_cxc_report`  
Ruta Odoo: `Contabilidad -> Informes`  
Dashboard: `Tableros -> Finance -> CxC Gerencial`

Este documento explica el uso operativo del reporte gerencial de Cuentas por Cobrar y del plan de accion editable.

---

## 1. Generar la informacion del corte

Antes de usar el dashboard, se debe generar el snapshot CxC.

1. Ir a `Contabilidad -> Informes -> CxC por Cliente DEV`.
2. Seleccionar la `Fecha de corte`.
3. Presionar `Ver reporte`.

Al hacer esto, Odoo calcula la cartera desde la contabilidad publicada hasta esa fecha:

- Saldos por cliente.
- Aging en buckets: `No vencido`, `1-15`, `16-30`, `31-45`, `46-60`, `61-90`, `91+`.
- Cartera neta, cartera bruta, saldo a favor y vencido positivo.
- `Sobrelimite` (limite de credito menos cartera neta), `Valor consig.` y `Cartera+Consig.`.
- Riesgo, prioridad y accion recomendada.
- Plan de accion editable por cliente.

Importante: si se vuelve a generar el mismo corte, Odoo recalcula los saldos contables, pero conserva los campos editables del plan de accion como estado, responsable, comentarios y fechas de seguimiento.

---

## 2. Revisar la consulta CxC

Despues de generar el corte, Odoo abre la vista `Cuentas por Cobrar por Cliente`.

Tambien se puede abrir desde:

`Contabilidad -> Informes -> Consulta CxC por Cliente DEV`

Campos principales:

| Campo | Uso |
|---|---|
| `Cartera neta` | Saldo total del cliente, incluyendo saldos a favor. |
| `Cartera bruta` | Solo saldos positivos por cobrar. |
| `Saldo a favor` | Creditos o saldos negativos del cliente. |
| `No vencido` | Saldo que aun no vence al corte. |
| `Vencido` | Saldo vencido positivo. |
| `1-15` a `91+` | Distribucion de antiguedad. |
| `Sobrelimite` | Limite de credito menos cartera neta. Positivo = cupo disponible; negativo = excede el limite. |
| `Valor consig.` | Valor de la mercancia que el cliente tiene en consignacion. |
| `Cartera+Consig.` | Cartera neta + valor consignacion. Exposicion total de riesgo. |
| `% Vencido` | Proporcion del vencido sobre la cartera bruta. |
| `Riesgo` | Clasificacion automatica del cliente. |
| `Prioridad` | P1, P2, P3 o P4 para gestion de cobro. |

Botones utiles:

| Boton | Funcion |
|---|---|
| `Detalle` | Abre los documentos pendientes del cliente. |
| `Plan` | Abre el plan de accion editable del cliente. |

Filtros recomendados:

- `Solo vencidos`
- `P1`
- `Restriccion credito`
- Agrupar por `Vendedor`
- Agrupar por `Riesgo`
- Agrupar por `Prioridad`

---

## 3. Usar el Dashboard Spreadsheet

Abrir:

`Tableros -> Finance -> CxC Gerencial`

El dashboard tiene estas hojas:

| Hoja | Que muestra |
|---|---|
| `Resumen Gerencial` | KPIs, composicion de aging y top clientes vencidos. |
| `Resumen Vendedor` | Saldos y vencidos agrupados por vendedor. |
| `Ranking Clientes` | Top por cartera bruta y top por vencido. |
| `Plan Accion` | Lectura del plan operativo de cobro. |
| `Base CxC` | Tabla base para auditoria y revision detallada. |

Filtros globales del dashboard:

- `Fecha corte`
- `Compania`
- `Vendedor`

Los filtros por `Riesgo`, `Prioridad` y `Estado` se aplican desde las vistas Odoo enlazadas (`Consulta CxC por Cliente DEV` y `Plan de Accion CxC DEV`), donde esos campos son filtros y agrupadores nativos.

Uso recomendado:

1. Filtrar por `Fecha corte`.
2. Revisar KPIs generales en `Resumen Gerencial`.
3. Revisar vendedores con mayor vencido en `Resumen Vendedor`.
4. Entrar a `Ranking Clientes` para identificar concentracion.
5. Pasar a `Plan Accion` para revisar a quien se debe gestionar.

Nota: el dashboard es para analisis. La edicion formal del seguimiento se realiza en la lista/formulario de Odoo, no escribiendo en celdas libres.

---

## 4. Gestionar el Plan de Accion

Abrir desde:

`Contabilidad -> Informes -> Plan de Accion CxC DEV`

Cada fila representa un cliente en una fecha de corte.

Campos calculados por Odoo:

- Cliente.
- Vendedor.
- Cartera neta.
- Cartera bruta.
- Vencido.
- `91+`.
- Riesgo.
- Prioridad.
- Accion recomendada.
- Responsable sugerido.
- Restriccion de credito.

Campos editables por el equipo de CxC:

| Campo | Como usarlo |
|---|---|
| `Estado` | Indicar avance de la gestion. |
| `Responsable` | Usuario encargado de dar seguimiento. |
| `Fecha compromiso` | Fecha limite para obtener pago o respuesta. |
| `Fecha ultimo contacto` | Ultima fecha en que se contacto al cliente. |
| `Monto prometido` | Monto que el cliente prometio pagar. |
| `Fecha promesa pago` | Fecha prometida por el cliente. |
| `Comentarios` | Notas de llamada, acuerdos o escalaciones. |

Estados sugeridos:

| Estado | Uso |
|---|---|
| `Pendiente` | Caso sin gestion. |
| `Contactado` | Ya se contacto al cliente. |
| `Promesa de pago` | Cliente dio fecha o monto de pago. |
| `Pagado` | Caso normalizado. |
| `Credito bloqueado` | Se restringe credito o despacho. |
| `Escalado` | Caso elevado a jefatura o gerencia. |
| `Cerrado` | Caso finalizado. |

---

## 5. Prioridades de gestion

| Prioridad | Significado | Accion recomendada |
|---|---|---|
| `P1` | Riesgo critico, alto o depuracion critica. | Gestion inmediata, posible bloqueo de credito y escalacion. |
| `P2` | Riesgo medio. | Llamada de cobro y compromiso fechado. |
| `P3` | Riesgo bajo o preventivo estrategico. | Seguimiento preventivo. |
| `P4` | Al dia, saldo a favor o sin saldo. | Monitoreo o depuracion contable. |

Fechas compromiso iniciales:

| Prioridad | Fecha sugerida |
|---|---|
| `P1` | Fecha de generacion + 2 dias |
| `P2` | Fecha de generacion + 5 dias |
| `P3` | Fecha de generacion + 10 dias |
| `P4` | Fecha de generacion + 15 dias |

---

## 6. Rutina recomendada para CxC

Diario:

1. Abrir `Plan de Accion CxC DEV`.
2. Filtrar `P1` y `Pendiente`.
3. Contactar clientes de mayor vencido.
4. Registrar comentario, fecha de contacto y promesa de pago.
5. Cambiar estado segun avance.

Semanal:

1. Revisar `Resumen Vendedor`.
2. Agrupar por vendedor y prioridad.
3. Revisar compromisos vencidos.
4. Escalar casos P1 sin avance.
5. Depurar saldos a favor y clientes marcados como inactivos/no usar.

Mensual:

1. Generar nuevo corte.
2. Comparar cartera bruta, vencido y `91+`.
3. Revisar top 10 clientes vencidos.
4. Actualizar responsables.
5. Cerrar casos pagados o normalizados.

---

## 7. Exportar a Excel

Desde el asistente `CxC por Cliente DEV`:

1. Seleccionar fecha de corte.
2. Presionar `Exportar Excel`.

El archivo exportado contiene la base por cliente con las columnas principales del analisis.

Para analisis ejecutivo, usar preferiblemente el Spreadsheet `CxC Gerencial`.

---

## 8. Validaciones importantes

Antes de tomar decisiones de cobro o bloqueo:

- Confirmar que el corte usado es el correcto.
- Revisar el detalle del cliente con el boton `Detalle`.
- Validar notas de credito o saldos a favor.
- Revisar si el cliente esta inactivo o asignado a un vendedor `NO USAR`.
- Confirmar si existen pagos recientes posteriores a la fecha de corte.

El dashboard muestra la foto contable al corte seleccionado; no necesariamente refleja pagos registrados despues de esa fecha.

Efecto del bloqueo de credito: al bloquear un cliente desde el Plan de Accion, el sistema impide **confirmar ordenes de venta** y **validar facturas/recibos de cliente** de ese cliente (y de su empresa para los contactos hijos). Las notas de credito siguen permitidas. El bloqueo es manual y persistente: se libera desde el boton `Liberar credito` del Plan de Accion.
