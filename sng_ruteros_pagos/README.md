# SNG Ruteros — Recibos de pago

Guía de uso del módulo `sng_ruteros_pagos` para Odoo 18.

## ¿Qué hace este módulo?

Recibe los **recibos de pago que los ruteros (vendedores de ruta) registran desde la app móvil** y los guarda en Odoo como pagos de cliente (`account.payment`). Además:

- Guarda los datos capturados en la app: método de pago, referencia, observaciones, saldos y vendedor.
- Agrega el menú **Ruteros → Recibos** para revisar todos los recibos que llegan de la app.
- **Aplica (concilia) el pago contra las facturas del cliente** automáticamente al confirmarlo, si la app indicó a qué facturas corresponde.

---

## Flujo de trabajo

```
App móvil (rutero cobra)          Odoo (oficina)
─────────────────────────         ─────────────────────────────
1. Registra el recibo      ──►    2. Llega como pago CONFIRMADO
                                     (con asiento contable) y, si
                                     trae facturas, ya APLICADO ✔
                                  3. Se revisa en Ruteros → Recibos
```

### 1. El rutero cobra en la app

El rutero registra el cobro en la app móvil indicando cliente, monto, método de pago, referencia y (opcionalmente) las facturas que está cobrando. El recibo llega a Odoo como un **pago ya confirmado** (estado *En proceso*) con su asiento contable generado. Si la app indicó las facturas, el módulo las **concilia automáticamente en ese mismo momento** — no hay que hacer nada en la oficina.

### 2. Revisar los recibos en Odoo

Ir al menú **Ruteros → Recibos**. Ahí aparecen únicamente los pagos creados desde la app, con filtros útiles:

- **Borrador / Confirmado** — para separar lo pendiente de lo ya contabilizado.
- **Hoy** — los cobros del día.
- Agrupar por **Vendedor**, **Cliente**, **Diario** o **Estado** (por ejemplo, para cuadrar la liquidación diaria de cada rutero).

Los estados del pago en Odoo 18 son: **Borrador** (sin contabilizar), **En proceso** (confirmado, asiento generado — así llegan de la app), **Pagado** (cobro consumado/conciliado), **Cancelado** y **Rechazado**.

Al abrir un recibo, el bloque **"Recibo Ruteros (app)"** muestra lo que capturó el rutero:

| Campo | Contenido |
|---|---|
| Método (app) | Efectivo, transferencia, SINPE, etc. según la app |
| Referencia (app) | Número de comprobante o transferencia |
| Vendedor (app) | Rutero que hizo el cobro |
| Saldo anterior / proyectado | Saldo del cliente antes y después del cobro |
| Observaciones (app) | Notas del rutero |
| Facturas a pagar | Facturas del cliente a las que se aplicará el pago |

### 3. ¿Y si un recibo llega en borrador?

Normalmente no ocurre (la app los manda confirmados), pero si un pago quedara en *Borrador*, basta pulsar **Confirmar**: el módulo genera el asiento y, si el recibo trae **Facturas a pagar**, las concilia automáticamente en ese momento.

### 4. Aplicar a facturas después (botón manual)

Si un pago se confirmó **sin** facturas, o hay que agregarle más:

1. Abrir el pago confirmado.
2. En **Facturas a pagar**, agregar las facturas pendientes del cliente (solo aparecen las publicadas con saldo).
3. Pulsar el botón **Aplicar a facturas** del encabezado.

---

## Requisitos para que la aplicación a facturas funcione

1. **La factura debe estar publicada y con saldo pendiente.** Facturas en borrador o ya pagadas no se pueden aplicar.
2. **El diario del pago debe tener configurada su cuenta transitoria de cobros** (Contabilidad → Configuración → Diarios → pestaña *Pagos entrantes*). Sin ella, Odoo 18 no genera asiento contable y el pago queda ligado a la factura solo de forma informativa, sin conciliar.

## Casos frecuentes

- **El cobro no cubre toda la factura** → la factura queda **En pago parcial** con el saldo restante; no hay que hacer nada más.
- **El cobro cubre varias facturas** → se agregan todas en *Facturas a pagar*; Odoo las aplica en orden hasta agotar el monto.
- **El rutero no indicó facturas** → el pago queda como saldo a favor del cliente. Se puede aplicar después con el botón **Aplicar a facturas**, o desde la factura con "Pagos pendientes".
- **Recibo con error** → mientras esté en *Borrador* se puede corregir o cancelar. Si ya está confirmado, usar *Restablecer a borrador* (esto deshace la conciliación).

---

## Matching IA de facturas (Claude)

Cuando el puente no logra ligar algún número de factura del texto de la app (typos, ceros faltantes, números incompletos), el pago queda marcado como **Matching IA: Pendiente** y un cron (cada 10 minutos) consulta la API de Claude (Anthropic) para emparejar esos números contra las **facturas abiertas reales del cliente**.

- La IA **solo sugiere**: las coincidencias de confianza **alta** se agregan a *Facturas a pagar* pero **no se concilian** — la conciliación sigue requiriendo el botón **Aplicar a facturas** (o confirmar el pago). El detalle completo (número capturado → factura, confianza y razón) queda en el chatter.
- En Python se re-validan los IDs devueltos: la IA no puede ligar una factura que no esté en la lista de candidatas abiertas del cliente.
- También hay un botón manual **Buscar facturas con IA** en el pago. Si el pago no tiene números capturados, la IA sugiere por coincidencia de montos (confianza máxima *media*).
- Estados posibles: *Pendiente* → *Sugerencia lista* / *Sin coincidencia* / *Error* (con filtros propios en Ruteros → Recibos).

### Configuración

1. Instalar la librería en el venv de Odoo: `pip install anthropic` (ya declarada como dependencia externa del módulo).
2. En **Ajustes → Técnico → Parámetros del sistema**, editar `sng_ruteros_pagos.anthropic_api_key` y reemplazar `PENDIENTE_CONFIGURAR` por la API key de [platform.claude.com](https://platform.claude.com). Mientras no se configure, el cron no hace nada (solo deja un aviso en el log).
3. Opcional: `sng_ruteros_pagos.anthropic_model` define el modelo (por defecto `claude-opus-4-8`).

---

## Para el desarrollador de la app (referencia técnica)

La app crea el pago vía API (XML-RPC / JSON-RPC) sobre `account.payment` y lo confirma. La conciliación automática se dispara tanto si el pago se crea ya confirmado como si se confirma después con `action_post` o escribiendo el estado. Requisitos del payload:

> ⚠️ **Importante:** la app debe enviar `sng_from_app: true`. Sin esa bandera el pago no aparece en el menú *Ruteros → Recibos* y **no se aplica a facturas automáticamente**.

Para que quede ligado a facturas, incluir `invoice_ids` en el payload de creación:

```json
{
  "payment_type": "inbound",
  "partner_type": "customer",
  "partner_id": 123,
  "amount": 5000.0,
  "journal_id": 7,
  "sng_from_app": true,
  "sng_metodo_pago": "SINPE",
  "sng_referencia": "2026072012345",
  "sng_vendedor_id": 15,
  "sng_saldo_anterior": 12000.0,
  "sng_saldo_proyectado": 7000.0,
  "sng_observaciones": "Cobro ruta norte",
  "invoice_ids": [[6, 0, [456, 789]]]
}
```

- `invoice_ids` usa el formato de comandos de Odoo: `[[6, 0, [ids...]]]` reemplaza la lista completa.
- La conciliación se dispara automáticamente: al **crear** el pago si ya viene confirmado (`in_process`/`paid`), o al **confirmarlo después** (`action_post` o escritura del estado).
- Si la app no envía `invoice_ids`, entra el **puente**: el módulo parsea el bloque `Facturas: NUM[A:../P:../S:..]` de `sng_observaciones` (o del memo), busca cada número por `name` de factura publicada dentro de la compañía del pago y del árbol de contactos del cliente, y llena `invoice_ids` automáticamente. Números que no matcheen de forma única se reportan en el chatter del pago (no bloquean el guardado) y el pago queda como anticipo. Cuando la app empiece a mandar `invoice_ids`, el puente deja de intervenir solo.

## Campos técnicos que agrega el módulo

| Campo | Tipo | Descripción |
|---|---|---|
| `sng_from_app` | Boolean | Marca los pagos creados desde la app (filtra el menú Ruteros) |
| `sng_metodo_pago` | Char | Método de pago capturado en la app |
| `sng_referencia` | Char | Referencia / comprobante |
| `sng_observaciones` | Text | Observaciones del rutero |
| `sng_saldo_anterior` | Monetary | Saldo del cliente antes del cobro |
| `sng_saldo_proyectado` | Monetary | Saldo proyectado después del cobro |
| `sng_vendedor_id` | Many2one → `res.partner` | Rutero que registró el cobro. Es el **contacto** marcado como vendedor (`is_salesperson`, lógica de `sales_commission_omax`), no un usuario |

*(Las facturas se ligan con el campo nativo `invoice_ids` de Odoo 18; el módulo agrega la conciliación automática al confirmar.)*
