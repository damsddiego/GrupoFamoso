# Guía de Usuario: Rastreo de Documentos Rechazados por Hacienda

## ¿Qué hace este módulo?

Cuando Hacienda rechaza una factura electrónica o una nota de crédito, este módulo le permite:

- Ver todos los documentos rechazados (facturas y notas de crédito) en un solo lugar
- Crear un documento de reemplazo a partir del rechazado
- Vincular un documento existente (ya aceptado) como reemplazo
- Consultar el historial completo de intentos de reemplazo
- Seguimiento automático del estado en Hacienda del documento de reemplazo

---

## Acceso

Vaya a **Facturación → Clientes → Documentos Rechazados Hacienda**

Encontrará dos submenús:

| Submenú | Descripción |
|---------|-------------|
| **Documentos Rechazados** | Lista de todas las facturas y notas de crédito rechazadas con su estado de reemplazo |
| **Historial de Reemplazos** | Registro cronológico de todos los vínculos entre documentos rechazados y sus reemplazos |

---

## Flujo de trabajo

### Opción A: Crear un documento de reemplazo nuevo

Use esta opción cuando necesita generar una nueva factura o nota de crédito basada en la rechazada.

1. Abra el documento rechazado (desde el menú **Documentos Rechazados** o desde la lista general de facturas)
2. Vaya a la pestaña **Reemplazo Hacienda**
3. Haga clic en **Crear Factura de Reemplazo**
4. Se abrirá un nuevo documento en borrador con los mismos datos del original (cliente, líneas, impuestos), pero sin datos electrónicos
5. Revise y ajuste lo que sea necesario (por ejemplo, corregir el motivo del rechazo)
6. Confirme el documento y envíelo a Hacienda normalmente
7. Cuando Hacienda responda, el estado del historial se actualizará automáticamente a "Aceptado" o "Rechazado"

> **Importante:** El nuevo documento se crea como el mismo tipo del original. Si el documento rechazado es una factura, el reemplazo será una factura. Si es una nota de crédito, será una nota de crédito.

### Opción B: Vincular un documento existente

Use esta opción cuando ya creó manualmente un documento de reemplazo y fue aceptado por Hacienda.

1. Abra el documento rechazado
2. Vaya a la pestaña **Reemplazo Hacienda**
3. Haga clic en **Vincular Factura Existente**
4. En el asistente, seleccione el documento de reemplazo
5. Opcionalmente agregue notas explicativas
6. Haga clic en **Vincular Reemplazo**

> **Nota:** El asistente solo muestra documentos del mismo tipo, aceptados por Hacienda y de la misma compañía. Si el rechazado es una factura, solo verá facturas. Si es una nota de crédito, solo verá notas de crédito.

---

## Pestaña "Reemplazo Hacienda"

Esta pestaña aparece automáticamente en cualquier factura o nota de crédito que haya sido rechazada por Hacienda. Contiene:

| Campo | Descripción |
|-------|-------------|
| **Estado de Reemplazo** | `Pendiente de Reemplazo` — aún no tiene reemplazo. `Reemplazada` — ya fue reemplazada exitosamente |
| **Intentos de Reemplazo** | Cantidad de veces que se ha intentado reemplazar este documento |
| **Reemplazada por** | Enlace directo al documento de reemplazo actual (solo visible cuando el estado es "Reemplazada") |

### Botones de acción

Estos botones aparecen cuando el documento está pendiente de reemplazo:

| Botón | Acción |
|-------|--------|
| **Crear Factura de Reemplazo** | Crea una copia del documento rechazado en estado borrador, sin datos electrónicos |
| **Vincular Factura Existente** | Abre el asistente para seleccionar un documento ya aceptado por Hacienda |
| **Ver Historial Completo** | Abre la lista completa de intentos de reemplazo (siempre visible) |

### Tabla de historial

Debajo de los botones se muestra la tabla de historial con todos los intentos, incluyendo: número de intento, documento de reemplazo, estado, si es el actual, fecha, usuario y notas.

---

## Estados del historial de reemplazo

| Estado | Significado | ¿Cómo se asigna? |
|--------|-------------|-------------------|
| **Borrador** | Se creó el documento de reemplazo pero aún no se envía a Hacienda | Automático al usar "Crear Factura de Reemplazo" |
| **Vinculado** | Se vinculó manualmente un documento existente ya aceptado | Automático al usar "Vincular Factura Existente" |
| **Aceptado por Hacienda** | El documento de reemplazo fue aceptado | Automático cuando Hacienda responde con aceptación |
| **Rechazado por Hacienda** | El documento de reemplazo también fue rechazado | Automático cuando Hacienda responde con rechazo |
| **Cancelado** | El intento de reemplazo fue cancelado | Manual por el usuario |

> Los estados **Aceptado** y **Rechazado** se sincronizan automáticamente con la respuesta de Hacienda. No necesita actualizar el historial manualmente.

---

## Múltiples intentos

Si el primer reemplazo también es rechazado por Hacienda, puede crear otro intento:

1. Abra el documento rechazado original
2. En la pestaña **Reemplazo Hacienda**, los botones de acción volverán a estar disponibles
3. Cree o vincule un nuevo reemplazo
4. El intento anterior queda registrado en el historial para auditoría

Solo el intento más reciente se marca como "actual". Los anteriores se conservan como referencia histórica.

---

## Identificar documentos de reemplazo

Cuando una factura o nota de crédito es un reemplazo de otra, aparece el campo **Reemplaza a** en la parte superior del formulario, con un enlace directo al documento rechazado original. Esto permite navegar fácilmente entre ambos documentos.

---

## Filtros disponibles

En la vista de documentos rechazados puede usar los siguientes filtros:

| Filtro | Descripción |
|--------|-------------|
| **Rechazados por Hacienda** | Todos los documentos rechazados (activo por defecto) |
| **Pendientes de Reemplazo** | Rechazados que aún no tienen reemplazo |
| **Reemplazados** | Rechazados que ya fueron reemplazados exitosamente |
| **Solo Facturas** | Muestra solo facturas (excluye notas de crédito) |
| **Solo Notas de Crédito** | Muestra solo notas de crédito (excluye facturas) |

También puede agrupar por **Estado de Reemplazo** desde el menú "Agrupar por".

---

## Notificaciones en el chatter

Cada vez que se crea o vincula un reemplazo, se registra automáticamente un mensaje en el chatter de **ambos** documentos (el rechazado y el de reemplazo) con los siguientes detalles:

- Número de intento
- Clave electrónica del documento
- Usuario que realizó la vinculación
- Fecha y hora

Esto permite tener trazabilidad completa directamente en el historial de mensajes de cada documento.

---

## Permisos

| Rol | Puede ver | Puede crear/editar | Puede eliminar |
|-----|-----------|-------------------|----------------|
| **Facturación / Usuario** | Si | Si | No |
| **Facturación / Gerente** | Si | Si | Si |

---

## Preguntas frecuentes

**¿Puedo eliminar un vínculo de reemplazo?**
Solo los usuarios con rol de Gerente de Contabilidad pueden eliminar registros del historial.

**¿Qué pasa si borro el documento de reemplazo?**
El registro de historial se mantiene pero el campo de documento de reemplazo queda vacío. El documento rechazado vuelve a estado "Pendiente de Reemplazo".

**¿Puedo usar un mismo documento para reemplazar dos documentos rechazados?**
No. Un documento de reemplazo solo puede estar vinculado a un documento rechazado.

**¿El módulo envía el documento de reemplazo automáticamente a Hacienda?**
No. El documento de reemplazo se crea en borrador. Usted debe confirmarlo y enviarlo a Hacienda siguiendo el proceso normal de facturación electrónica.

**¿Puedo vincular una factura como reemplazo de una nota de crédito (o viceversa)?**
No. El reemplazo debe ser del mismo tipo: una factura reemplaza a una factura, y una nota de crédito reemplaza a una nota de crédito.

**¿Necesito actualizar manualmente el estado del historial cuando Hacienda responde?**
No. El estado se sincroniza automáticamente. Cuando Hacienda acepta o rechaza el documento de reemplazo, el historial se actualiza solo.

**¿Qué pasa si la factura original fue rechazada pero luego reintentada y aceptada por el módulo de facturación electrónica?**
El módulo también detecta documentos con el indicador de rechazo histórico (`FE Rechazada`), incluso si el estado tributario ya no es "rechazado". La pestaña de Reemplazo Hacienda seguirá visible en estos casos.
