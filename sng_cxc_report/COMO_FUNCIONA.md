# Módulo SNG CxC Report — Guía de Funcionamiento

**Versión:** 18.0.1.1.0  
**Módulo:** `sng_cxc_report`  
**Ubicación:** `odoo18-custom-addons/sng_cxc_report/`  
**Base de datos:** prod_gf (Grupo Famoso, multi-compañía)

> Adaptación Grupo Famoso: el vendedor asignado (`assigned_salesperson_id`)
> es un campo por compañía en esta instancia, así que el reporte lo resuelve
> con la compañía de cada apunte. El DPP sigue viniendo de
> `regalarte_customer_metrics`, que también está instalado aquí.

---

## ¿Qué hace este módulo?

Genera un **análisis gerencial de Cuentas por Cobrar (CxC)** a una fecha de corte específica. Por cada cliente con saldo, calcula:

- Aging por 7 buckets de vencimiento
- Nivel de riesgo y prioridad de cobro automáticos
- Acción recomendada y responsable sugerido
- Plan de acción persistente con seguimiento de gestiones
- **Bloqueo de crédito** directo desde el plan de acción, que impide confirmar órdenes de venta **y validar facturas de cliente**

---

## Menús en Odoo

`Contabilidad → Informes`

| Nombre | Función |
|---|---|
| **CxC por Cliente DEV** | Abre el asistente para generar el análisis |
| **Consulta CxC por Cliente DEV** | Vista del snapshot generado |
| **Plan de Accion CxC DEV** | Plan de acción editable con seguimiento de cobro |

---

## Flujo de uso paso a paso

```
1. Asistente → ingresar fecha de corte → clic "Ver reporte" o "Exportar Excel"
        ↓
2. El sistema genera snapshot: una fila por cliente con todo el aging
        ↓
3. Post-procesamiento: calcula riesgo, prioridad, acción recomendada
        ↓
4. Crea/actualiza Plan de Acción por cliente
        ↓
5. CxC trabaja el Plan: actualiza estado, registra contactos, bloquea crédito
        ↓
6. Ventas confirma orden / Contabilidad valida factura → sistema verifica bloqueo → rechaza si aplica
```

---

## Paso 1 — Generar el análisis

En el asistente (`CxC por Cliente DEV`):

- **Fecha de corte**: el análisis toma todos los apuntes contables publicados hasta esa fecha
- **Ver reporte**: abre la vista lista en pantalla
- **Exportar Excel**: descarga un `.xlsx` con el mismo contenido

Al ejecutar, el sistema:
1. Elimina el snapshot anterior para esa fecha y compañía
2. Recalcula desde cero con los datos actuales de la BD
3. Crea o actualiza un Plan de Acción por cada cliente

---

## Paso 2 — El snapshot (tabla `sng_cxc_report`)

Cada fila representa **un cliente a la fecha de corte**. Los datos son inmutables (foto del momento).

### Campos de aging

| Campo | Descripción |
|---|---|
| `total_receivable` | Cartera neta (puede ser negativo si hay saldos a favor) |
| `gross_receivable` | Cartera bruta = parte positiva del neto del cliente (`max(0, total_receivable)`) |
| `credit_balance` | Saldo a favor **neto**: lo que le sobra al cliente tras saldar toda su deuda (`abs(min(0, total_receivable))`). Solo es > 0 cuando el crédito supera la deuda |
| `over_limit_amount` | **Sobrelimite** = `credit_limit − total_receivable`. Positivo = cupo disponible; negativo = excede el límite |
| `consignment_value` | Valor de la mercancía en consignación del cliente (cantidad × precio de lista) |
| `total_exposure` | **Cartera neta + Consig.** = `total_receivable + consignment_value`. Exposición total de riesgo |
| `not_due_amount` | Porción no vencida (vence después del corte) |
| `positive_overdue_amount` | Vencido positivo total |
| `bucket_1_15` | Vencido 1–15 días |
| `bucket_16_30` | Vencido 16–30 días |
| `bucket_31_45` | Vencido 31–45 días |
| `bucket_46_60` | Vencido 46–60 días |
| `bucket_61_90` | Vencido 61–90 días |
| `bucket_91_plus` | Vencido 91+ días |
| `overdue_ratio` | % vencido = `positive_overdue / gross_receivable` |
| `bucket_91_ratio` | % en bucket 91+ |
| `dominant_bucket` | Bucket con el mayor importe |
| `weighted_overdue_days` | Días de mora ponderados (promedio pesado por saldo) |

### Cómo se calcula el aging

La fuente es `account.move.line` con:
- `account_type = 'asset_receivable'`
- `move_id.state = 'posted'`
- `date <= fecha_de_corte`

Las conciliaciones parciales (`account_partial_reconcile`) se descuentan al saldo de cada línea con `max_date <= fecha_de_corte`, lo que da el **saldo real a esa fecha** aunque hoy ya esté pagado.

Los buckets se calculan con `COALESCE(date_maturity, date)` como fecha de vencimiento.

---

## Paso 3 — Clasificación automática

### Niveles de riesgo (`risk_level`)

| Riesgo | Condición |
|---|---|
| `Sin saldo` | `gross_receivable = 0` y sin créditos |
| `Saldo a favor` | `gross_receivable = 0` pero hay saldo negativo |
| `Al día` | `positive_overdue = 0` y cartera bruta < ₡2 M |
| `Preventivo estratégico` | `positive_overdue = 0` y cartera bruta ≥ ₡2 M |
| `Bajo` | % vencido pequeño, días mora bajos y montos menores |
| `Medio` | `% vencido ≥ 15%` o mora ≥ 16 días o vencido ≥ ₡300 K |
| `Alto` | `bucket_61_90 > 0` o mora ≥ 46 días o vencido ≥ ₡1 M o `% ≥ 50%` |
| `Crítico` | `bucket_91 > 0` o `% vencido ≥ 80%` o vencido ≥ ₡2.5 M |
| `Depuración crítica` | Cliente inactivo/no-usar con saldo en 91+ |

### Prioridades (`priority`)

| Prioridad | Riesgos incluidos |
|---|---|
| **P1** | Crítico, Alto, Depuración crítica |
| **P2** | Medio |
| **P3** | Bajo, Preventivo estratégico |
| **P4** | Al día, Saldo a favor, Sin saldo |

### Detección de flags especiales

| Flag | Condición |
|---|---|
| `inactive_flag` | Nombre del cliente contiene "INACT" |
| `no_use_flag` | Nombre del vendedor contiene "NO USAR" o es "OFICINA" |

### Días de mora ponderados

```
weighted_days = (
    bucket_1_15  × 8  +
    bucket_16_30 × 23 +
    bucket_31_45 × 38 +
    bucket_46_60 × 53 +
    bucket_61_90 × 75 +
    bucket_91    × 120
) / positive_overdue_amount
```

---

## Paso 4 — Plan de Acción (`sng.cxc.action.plan`)

Modelo **persistente** (no es un snapshot): mantiene el historial de gestiones aunque se regenere el análisis.

### Campos financieros (readonly, se actualizan con cada nuevo análisis)

Cartera neta, bruta, saldo a favor, vencido, 91+, % vencido, bucket dominante, días mora ponderados, riesgo, prioridad, acción recomendada, responsable sugerido.

### Campos de gestión (editables por CxC)

| Campo | Descripción |
|---|---|
| `state` | Estado de la gestión (ver estados abajo) |
| `responsible_id` | Gestor de cobro asignado |
| `commitment_date` | Fecha compromiso de pago |
| `last_contact_date` | Fecha del último contacto |
| `promised_amount` | Monto comprometido por el cliente |
| `promised_payment_date` | Fecha prometida de pago |
| `comments` | Notas libres de gestión |

### Estados del plan

```
Pendiente → Contactado → Promesa de pago → Pagado
                     ↘ Bloqueado → Escalado → Cerrado
```

| Estado | Uso |
|---|---|
| `Pendiente` | Recién creado, aún no gestionado |
| `Contactado` | Se realizó contacto con el cliente |
| `Promesa de pago` | El cliente dio fecha y monto de pago |
| `Bloqueado` | Crédito bloqueado en espera de regularización |
| `Pagado` | Cuenta normalizada |
| `Escalado` | Escalado a gerencia o instancia legal |
| `Cerrado` | Caso cerrado (cobrado o castigado) |

### Fechas de compromiso predeterminadas por prioridad

Al crear el plan, se asigna una fecha de compromiso inicial relativa a la fecha de generación:

| Prioridad | Plazo |
|---|---|
| P1 | +2 días |
| P2 | +5 días |
| P3 | +10 días |
| P4 | +15 días |

---

## Paso 5 — Bloqueo de crédito

### ¿Cómo funciona?

El bloqueo escribe el campo `sng_credit_blocked = True` en `res.partner`. Este campo se verifica en dos puntos:
- `sale.order.action_confirm` — al confirmar una orden de venta.
- `account.move._post` — al validar una **factura** (`out_invoice`) o **recibo** (`out_receipt`) de cliente.

Ambas verificaciones revisan tanto el contacto como su **partner comercial** (la empresa), de modo que el bloqueo de la empresa también frena la facturación a sus contactos hijos.

> Las **notas de crédito** (`out_refund`) **no** se bloquean, porque reducen la deuda del cliente.

```
Plan de Acción → botón "Bloquear crédito"
        ↓
partner.sng_credit_blocked = True
plan.state = 'bloqueado'
        ↓
Usuario intenta confirmar orden de venta o validar factura del cliente
        ↓
UserError: "El cliente X tiene el crédito bloqueado por CxC..."
```

### Botones en el formulario del plan

| Botón | Visible cuando | Efecto |
|---|---|---|
| **Bloquear crédito** (rojo) | El crédito NO está bloqueado | Bloquea + cambia estado a "Bloqueado" |
| **Liberar crédito** (verde) | El crédito SÍ está bloqueado | Libera + revierte estado a "Pendiente" |

También aparecen botones "Bloquear" / "Liberar" en la vista lista para acción rápida.

### Dónde se ve el bloqueo

1. **Plan de Acción**: campo `Credito bloqueado` + banner rojo en la parte superior del formulario
2. **Ficha del cliente** (`res.partner`): campo `Credito bloqueado (CxC)` con tracking de cambios
3. **Orden de venta**: mensaje de error al intentar confirmar
4. **Factura de cliente**: mensaje de error al intentar validar/publicar

---

## Paso 6 — Acciones recomendadas por nivel de riesgo

| Riesgo | Acción recomendada | Responsable |
|---|---|---|
| Crítico | Bloquear crédito, escalar a gerencia y formalizar convenio de pago en 48 horas | Jefatura CxC + Gerencia Comercial |
| Alto | Gestión intensiva de cobro; promesa formal de pago, revisión de línea y suspensión de despachos | CxC + Vendedor |
| Depuración crítica | Confirmar estatus comercial, bloquear crédito y definir recuperación o saneamiento contable | Jefatura CxC + Comercial |
| Medio | Llamada de cobro y envío de estado de cuenta; obtener compromiso fechado esta semana | Vendedor + CxC |
| Bajo | Recordatorio preventivo y confirmación de pago dentro de 3 a 5 días | Vendedor |
| Preventivo estratégico | Confirmar fecha de pago y enviar estado de cuenta preventivo por alto saldo | Vendedor + CxC |
| Al día | Monitoreo preventivo; confirmar próxima fecha de pago | Vendedor |
| Saldo a favor | Aplicar nota de crédito / compensar saldo y depurar antigüedad | CxC + Facturación |
| Sin saldo | Cerrar caso y dejar cuenta en monitoreo | CxC |

---

## Exportación a Excel

El botón **Exportar Excel** en el asistente genera un `.xlsx` con las siguientes columnas:

Código · Cliente · Vendedor · Última venta · Límite de crédito · Plazo · DPP · Cartera bruta · Saldo a favor · No vencido · Vencido · 1-15 · 16-30 · 31-45 · 46-60 · 61-90 · 91+ · **Cartera neta · Valor consig. · Cartera+Consig. · Sobrelimite** · Riesgo · Prioridad · Acción recomendada

> Las columnas **Cartera neta, Valor consig., Cartera+Consig. y Sobrelimite** se ubican después de `91+` (mismo orden en la vista lista en pantalla).

---

## Arquitectura del módulo

```
sng_cxc_report/
├── models/
│   ├── sng_cxc_report.py        # SngCxcReport + SngCxcReportLine + SngCxcActionPlan
│   ├── res_partner_ext.py        # Agrega sng_credit_blocked a res.partner
│   ├── sale_order_ext.py         # Bloquea action_confirm si crédito está bloqueado
│   └── account_move_ext.py       # Bloquea _post de factura/recibo si crédito está bloqueado
├── wizard/
│   └── sng_cxc_report_wizard.py  # Wizard de fecha de corte
├── views/
│   ├── sng_cxc_report_views.xml  # Todas las vistas (snapshot + plan de acción)
│   ├── sng_cxc_report_menus.xml  # 3 entradas en Contabilidad → Informes
│   └── sng_cxc_report_wizard_views.xml
├── security/
│   └── ir.model.access.csv       # Permisos por grupo contable
├── data/
│   ├── cxc_dashboard.xml         # Dashboard en Spreadsheet
│   └── files/cxc_dashboard.json  # Definición del dashboard
├── controllers/
│   └── main.py                   # Endpoint para descarga del Excel
└── static/src/js/
    └── action_manager.js         # Manejo de la descarga xlsx en el cliente
```

### Tablas en PostgreSQL

| Tabla | Tipo | Descripción |
|---|---|---|
| `sng_cxc_report` | Física con `_auto=False` | Snapshots por fecha de corte |
| `sng_cxc_report_line` | Física con `_auto=False` | Detalle por documento (apunte contable) |
| `sng_cxc_action_plan` | ORM estándar | Plan de acción persistente por cliente |

---

## Permisos

| Grupo | sng.cxc.report | sng.cxc.action.plan |
|---|---|---|
| `account.group_account_readonly` | Lectura | Lectura |
| `account.group_account_invoice` | Lectura | Lectura + Escritura + Creación |

El bloqueo de crédito usa `sudo()` internamente para poder escribir en `res.partner` independientemente del grupo del usuario que lo ejecuta.

---

## Consideraciones importantes

1. **El snapshot es compartido por fecha de corte y compañía**: no es por usuario. Todos los usuarios ven la misma foto de un corte dado; el campo `user_id` solo guarda quién lo generó por última vez (auditoría).

2. **Regenerar un corte borra el anterior**: ejecutar el wizard con la misma fecha elimina y recalcula ese snapshot para esas compañías (para todos los usuarios). El Plan de Acción (estado, comentarios, responsable) **se conserva**.

3. **El campo `sng_credit_blocked` persiste**: aunque se regenere el análisis, el bloqueo físico en el partner no se borra automáticamente. Debe liberarse manualmente desde el Plan de Acción.

4. **Clientes con múltiples compañías**: el snapshot respeta `allowed_company_ids` del contexto.

5. **Nota de créditos en aging**: las notas de crédito generan saldos negativos que aparecen como `credit_balance`. El vencido se calcula solo sobre saldos positivos (`positive_overdue_amount`).
