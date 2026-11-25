# CR Electronic Invoice Credit Limit

This module extends the Costa Rican Electronic Invoice module (`l10n_cr_cr_electronic_invoice`) to limit the creation of credit notes so that their total amount doesn't exceed the original invoice amount.

## Features

- Automatically computes the total amount of credit notes created for each invoice
- Prevents creation of credit notes that would cause the total credit amount to exceed the original invoice amount
- Shows the total credit notes amount on the invoice form view
- Provides clear error messages when limits are exceeded

## Functionality

### Credit Note Limitation
The module implements a constraint that checks:
1. When creating a credit note, it calculates the total amount of all existing credit notes for the same original invoice
2. It adds the current credit note amount to this total
3. If this sum exceeds the original invoice amount, it raises a validation error

### Computed Fields
- `credit_note_total`: Shows the total amount of credit notes created for an invoice

## Control de notas de crédito de cliente (18.0.2.0.0)

Una nota de crédito hecha desde la factura **no mueve inventario**. Toda
mercadería que regresa de un cliente entra por Devoluciones (`sng_return`).

- **Pregunta en el asistente de nota de crédito.** Si la factura ya se
  despachó, el asistente pregunta si la mercadería regresa a bodega. El código
  de referencia propone la respuesta (`reference.code.sng_politica_devolucion`):
  06 la fija en «Sí», 02, 09, 10 y 12 en «No», y el resto obliga a elegir.
  - «No»: se crea la nota de crédito como siempre, sin recepción.
  - «Sí»: no se crea la nota de crédito. Se abre una devolución en borrador con
    la mercadería de la factura; la nota de crédito (código 06) se genera desde
    Devoluciones cuando bodega valida la recepción.
- **Código 06 solo desde Devoluciones.** Una nota de crédito de cliente con un
  código de política «devuelve» no se puede confirmar si no viene de una
  devolución.
- **Anular y refacturar.** En facturas de cliente reemplaza al botón estándar
  «Revertir y crear factura» (que confirma la nota de crédito sin pasar por el
  comprobante electrónico). Crea la nota de crédito código 01 con el asistente
  estándar, la confirma con `action_post` (que la aplica a la factura) y deja
  la factura sustituta en borrador, ligada a la misma orden de venta y a la misma
  entrega. Si la confirmación pide un paso adicional, la sustituta se crea
  después con el botón «Crear factura sustituta» de la nota de crédito.
- **Motivo de anulación** (`sng.motivo.anulacion`) obligatorio al confirmar una
  nota de crédito de cliente con código 01. Se administra en
  Contabilidad → Configuración → Motivos de anulación.
- **Control de anulaciones** (Contabilidad → Clientes): notas de crédito con
  `sng_estado_control` «Sin refactura» (anulación total, con un motivo marcado
  «Requiere refactura», sin factura sustituta confirmada) o «Recepción pendiente» (recepciones que creaba la versión
  anterior del módulo y nadie validó ni canceló).

- **Solo usuarios autorizados crean notas de crédito de cliente.** Grupo
  «Crear notas de crédito de cliente» más una regla de registro global sobre
  `account.move`: quien no está en el grupo no puede crear una `out_refund`
  (desde la factura, desde Devoluciones ni por API) y no ve el botón «Nota de
  crédito» en las facturas de cliente. Puede verlas y puede solicitar una
  devolución. Los usuarios nuevos nacen sin el permiso.

Hasta la versión 18.0.1.1.0 el módulo creaba una recepción desde la ubicación
de clientes al confirmar cualquier nota de crédito sobre una factura
despachada. Los campos `return_location_id` y `stock_return_picking_id` se
conservan para esas notas de crédito y para las que genera `sng_return`.
Pasar a borrador o cancelar una de esas notas de crédito cancela su recepción
pendiente; si la recepción ya está validada, se bloquea.

## Installation

1. Add the module to your Odoo addons path
2. Update the apps list
3. Install the "CR Electronic Invoice Credit Limit" module

## Configuration

No additional configuration is required. The module works automatically once installed.

## Usage

1. When creating a credit note from an invoice, the system will automatically check if the total credit amount would exceed the original invoice
2. If the limit would be exceeded, a validation error is shown with details
3. On the invoice form view, you can see the total amount of credit notes already created

## Technical Details

The module extends:
- `account.move` model with computation and constraint methods
- `account.move.line` model with additional validation
- Invoice form view to display credit note totals

## Error Handling

When a credit note exceeds the allowed limit, a detailed error message is displayed showing:
- The total credit notes amount that would result
- The original invoice amount
- The current credit note amount
- The original invoice reference