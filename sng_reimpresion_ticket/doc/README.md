# SNG - Reimpresión de tickets de bodega

Pone dentro de Odoo la autorización de reimpresión que antes había que crear a
mano en la consola de Firebase.

## Por qué existe el control que este módulo respeta

El agente de impresión imprime cada orden **una sola vez**. No es una comodidad:
se estaban usando tickets duplicados para sacar mercadería dos veces. El agente
reclama la orden **antes** de mandar el papel a la impresora, así que una
impresión fallida igual cuenta como impresa. Falla cerrado a propósito: un ticket
que falta se nota y se pide; uno de más no se nota y se aprovecha.

Este módulo **no** relaja nada de eso. Solo mueve el trámite de autorizar a un
lugar donde queda registrado quién lo pidió.

## Cómo funciona

```
Odoo (botón, con permiso)
   -> POST al webhook de n8n con un token compartido
   -> n8n escribe /print_reprint_approvals/{orderId} en Firebase
   -> el agente lo detecta, consume el token dentro de su transacción
      e imprime un ticket marcado COPIA No.N / NO SURTIR DE NUEVO
```

Odoo **no** habla con Firebase directamente, y es deliberado. La credencial de
la base en tiempo real es de administrador total: quien la tenga puede borrar
`/print_ledger`, que es el registro que impide los duplicados. Dejándola solo en
n8n, un administrador de Odoo no gana ningún poder sobre el control.

La autorización es de un solo uso. Para un segundo intento hay que autorizar de
nuevo.

## Instalación

1. Copiar la carpeta a `odoo_addons/GrupoFamoso/` y actualizar la lista de
   aplicaciones.
2. Instalar **SNG - Reimpresión de tickets de bodega**.
3. Importar el workflow de n8n (ver abajo) y anotar su URL de producción.
4. En Odoo: *Ventas → Configuración → Ajustes → Reimpresión de tickets de
   bodega*. Llenar la URL del webhook y el token.
5. Dar el grupo *Autorizar reimpresión de tickets* a quien corresponda
   (*Ajustes → Usuarios*, sección **Impresión de tickets de bodega**).

## Workflow de n8n

`n8n_reprint_approval.workflow.json` se importa en n8n
(*Workflows → Import from File*). **Es un workflow nuevo e independiente: no
toca el de CasaFamosa.**

Antes de activarlo hay que reemplazar tres marcadores dentro del nodo
**Preparar**:

| marcador | valor |
| --- | --- |
| `__RTDB_URL__` | URL de la base en tiempo real, sin barra final |
| `__RTDB_SECRET__` | el secreto de esa base |
| `__TOKEN_ODOO__` | el mismo token que se puso en Odoo |

El token conviene que sea largo y aleatorio:

```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Max 256 }))
```

Después activar el workflow y copiar su **Production URL** a los ajustes de Odoo.

Para probar sin usar el botón:

```powershell
$body = @{ token = "<token>"; accion = "consultar"; orderId = 42808 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "<url>" -ContentType "application/json" -Body $body
```

## Qué ve el usuario

El botón **Reimprimir ticket** aparece en la orden de venta confirmada, solo
para quien tenga el permiso. Abre un asistente que:

- exige escribir un motivo, que sale impreso en el ticket;
- muestra cuántas copias existen ya, si se puede consultar el ledger;
- **advierte en rojo si la orden ya tiene mercadería despachada**, porque un
  ticket de alistado para algo que ya salió es justo el escenario del doble
  surtido. Se permite igual: el permiso es el control y la persona decide, pero
  queda registrada.

## Dónde queda el registro

Tres lugares independientes:

- **Odoo** — *Ventas → Reimpresiones de ticket* (`sng.reimpresion.log`). Incluye
  los intentos **fallidos**: se escriben en una transacción propia para que un
  error no borre la evidencia junto con el resto de la operación.
- **El chatter de la orden** — queda el mensaje de quién autorizó y por qué.
- **El agente** — `REIMPRESION_OK` en `/print_audit` y en `print_audit.jsonl`.

La bitácora de Odoo es de solo lectura para todos los grupos, incluido *Ajustes*.
Se crea con `sudo()` desde el asistente. Si alguna vez hace falta depurarla, va
por SQL o shell, a propósito.

### Leer los bloqueos sin asustarse

Cada reimpresión legítima deja uno o dos `DUPLICADO_BLOQUEADO` en la auditoría
del agente, sobre la misma orden y en los segundos siguientes al
`REIMPRESION_OK`. Es el uso único funcionando: al borrarse el nodo de
autorización el agente reintenta la orden y la rechaza. Lo que sí es señal de
alarma es un bloqueo **sin** un `REIMPRESION_OK` de la misma orden justo antes.

## Limitaciones conocidas

- **El token es una credencial al portador.** Quien lo consiga puede autorizar
  reimpresiones sin pasar por Odoo ni por el permiso. Vive en
  `ir.config_parameter`, que solo lee el grupo *Ajustes*; conviene rotarlo si
  alguien con ese grupo deja la empresa.
- **La consulta de copias previas es de cortesía.** Si Firebase o n8n no
  responden, el asistente lo dice y deja autorizar igual. La cuenta real la
  lleva el agente, que numera la copia con `max(local, remoto) + 1`.
- **El módulo no imprime.** Solo autoriza. Si el agente está caído, la
  autorización queda esperando y el ticket sale cuando el agente vuelve.
- La pantalla de ajustes se inserta con un `xpath` sobre
  `//app[@name='sale_management']`. Si una versión futura de Odoo cambia ese
  contenedor, los dos parámetros igual se pueden editar en *Ajustes → Técnico →
  Parámetros del sistema* (`sng_reimpresion.webhook_url`, `sng_reimpresion.token`).
