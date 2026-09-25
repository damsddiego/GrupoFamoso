# Manual de usuario — Control de Visitas y Rutas

Módulo `sng_control_visitas` · Odoo 18 · Grupo Famoso (multi-compañía)

Este manual explica cómo funciona el control de visitas de los agentes de ruta y el seguimiento de televentas en Odoo. Reemplaza la hoja de Excel "Matriz Control de visitas y rutas" y usa sus mismos conceptos: resultado de visita, motivo sin venta, próxima acción, comentario, seguimiento de televentas, estado de atención y alerta gerencial.

---

## 1. Para quién es y qué hace cada uno

| Rol | Quién | Qué hace en Odoo |
|---|---|---|
| Agente de ruta | Vendedores de ruta | No entra a Odoo. Registra la visita desde la **app de ruteros** en la tableta. |
| Televentas | Usuario configurado como "Responsable de televentas" (por defecto Call Center) | Atiende los **Seguimientos de televentas** que le llegan cada semana y los registra. |
| Gerencia | Usuarios del grupo "Control de visitas / Gerencia" | Revisa la **Matriz de Control**, los indicadores y el resumen semanal. Mantiene catálogos, rutas y frecuencias. |
| Oficina / facturación | Usuarios con permiso de facturación | Pueden consultar visitas, seguimientos y matriz, y completar datos de una visita si el agente no los envió. |

Todo está en el menú **Ruteros** de Odoo:

```
Ruteros
├── Recibos                 (ya existía)
├── Visitas                 (visitas de los agentes)
├── Seguimiento Televentas  (pendientes y llamadas de Natalia)
├── Matriz de Control       (la "matriz comercial" por cliente y mes)
└── Configuración           (solo gerencia)
    ├── Catálogos de visitas
    ├── Rutas y frecuencias
    └── Ajustes
```

---

## 2. Cómo fluye el proceso

```
 Agente visita al cliente ──▶ App envía la visita ──▶ Odoo la registra
                                                          │
             ┌────────────────────────────────────────────┘
             ▼
 ¿La visita pide televentas? (no visitado, reprogramada,
 o próxima acción "Transferir seguimiento a Natalia")
             │ sí
             ▼
 Se crea un SEGUIMIENTO PENDIENTE para la semana siguiente
 y una ACTIVIDAD en la bandeja de Natalia
             │
             ▼
 Natalia llama, registra canal, resultado, monto,
 próxima acción y comentario, y marca "Realizado"
             │
             ▼
 La MATRIZ mensual se recalcula todas las noches y
 el lunes se publica el RESUMEN GERENCIAL en Discuss
```

Además, cada domingo (cuando gerencia active ese proceso) Odoo genera automáticamente los pendientes de televentas de la semana que empieza para los clientes que **no fueron visitados** cuando tocaba, y para los clientes de televentas que llevan más tiempo del previsto sin contacto.

---

## 3. Visitas del agente

**Menú:** Ruteros › Visitas

Cada registro es una visita que la app envió. Odoo guarda la ubicación GPS, la hora, el cliente, el agente, y si hubo venta o cobro. El módulo agrega el bloque **Gestión comercial**:

| Campo | Qué es | Valores |
|---|---|---|
| Resultado de visita | Cómo terminó la visita comercialmente | Venta facturada · Pedido pendiente · Cotización enviada · Sin venta · No visitado · Visita reprogramada · Cliente cerrado · Bloqueado por cobro · Revisión de inventario · Visita bimensual |
| Monto venta visita | Monto vendido en la visita | Se llena solo con el total de la orden si hubo venta |
| Motivo sin venta | Por qué no compró | Lista del catálogo (16 motivos) |
| Próxima acción agente | Qué debe hacer el agente después | Lista del catálogo (14 acciones) |
| Fecha próxima acción | Cuándo debe hacerla | Fecha |
| Comentario predeterminado | Frase estándar del catálogo | Lista (20 frases) |
| Comentario agente | Texto libre | Obligatorio si no se eligió un predeterminado |
| Requiere seguimiento televentas | Natalia debe llamar la semana siguiente | Sí / No |
| Acción cerrada | La próxima acción ya fue atendida | Se marca sola o con el botón "Cerrar acción" |

**Reglas automáticas**

- Si la app no manda resultado de visita, Odoo lo deduce: venta con factura → *Venta facturada*; venta sin facturar → *Pedido pendiente*; lo demás → *Sin venta*. Cuando la orden se factura, *Pedido pendiente* pasa a *Venta facturada* solo.
- "Requiere seguimiento televentas" se activa solo cuando el resultado es *No visitado* o *Visita reprogramada*, o cuando la próxima acción es *Transferir seguimiento a Natalia*. En ese momento se crea el pendiente de televentas.
- Una visita nueva cierra la próxima acción pendiente de la visita anterior del mismo cliente.
- Si la app reenvía la misma visita por un corte de red, no se duplica.

**Filtros útiles:** Requiere televentas · Sin comentario · Acción vencida · Sin venta. Agrupar por resultado de visita, ruta o motivo sin venta.

**Si el agente no envió el bloque comercial:** un usuario de oficina puede abrir la visita y completarlo. Mientras tanto la visita cuenta como *Sin venta* y aparece en "Sin comentario".

---

## 4. Seguimiento de televentas (Natalia)

**Menú:** Ruteros › Seguimiento Televentas

Un seguimiento es una llamada que hay que hacer a un cliente en una semana concreta. Cada uno tiene:

- **Cliente**, **agente asignado** y **ruta** (se llenan solos).
- **Origen**: por qué existe. *Cliente no visitado*, *Visita pendiente según frecuencia*, *Solicitud del agente*, *Frecuencia de televentas* o *Manual*.
- **Semana** (lunes) y **fecha límite** (domingo de esa semana).
- **Responsable**: por defecto Natalia.
- **Estado**: Pendiente → Realizado, o Cancelado.

### 4.1 Cómo trabajar la lista

1. Entrar a Ruteros › Seguimiento Televentas. Por defecto muestra los **pendientes**. El filtro **Mis pendientes** deja solo los propios.
2. Los que están en rojo están **vencidos** (pasó la fecha límite o la fecha de próxima acción).
3. Abrir el seguimiento, llamar al cliente y completar el bloque **Gestión**:

| Campo | Valores |
|---|---|
| Fecha de contacto | Se llena con hoy si se deja vacía |
| Canal de contacto | Llamada · WhatsApp · Correo · Videollamada |
| Resultado televentas | Venta recuperada · Pedido pendiente · Cotización enviada · Sin interés · No respondió · Reprogramar llamada · Cliente cerrado · Datos incorrectos · Bloqueado por cobro · Inventario suficiente |
| Monto venta televentas | Monto si hubo venta |
| Orden de venta | Opcional, para enlazar el pedido |
| Próxima acción y fecha | Qué sigue y cuándo |
| Comentario predeterminado o comentario | **Uno de los dos es obligatorio** |

4. Pulsar **Marcar realizado**. Odoo cierra la actividad, marca como atendida la acción de la visita que originó el seguimiento y actualiza la fecha de último contacto del cliente.

**Reglas**

- No se puede marcar como realizado sin fecha, canal, resultado y comentario. Es la regla "toda llamada debe tener comentario".
- Si el resultado es *Reprogramar llamada* y se indica fecha de próxima acción, Odoo crea solo el siguiente pendiente para esa fecha.
- Solo puede haber un pendiente por cliente y semana.
- **Cancelar** se usa cuando la llamada ya no procede (cliente cerrado confirmado, duplicado). **Reabrir** devuelve un realizado o cancelado a pendiente.

### 4.2 Actividades

Cada pendiente crea una actividad "Seguimiento televentas" asignada a la responsable, con fecha límite. Aparece en el reloj de actividades de la barra superior de Odoo y en la vista **Actividad** del menú. Al marcar el seguimiento como realizado la actividad se cierra sola. No hace falta cerrarla a mano.

### 4.3 Otras vistas

- **Kanban** por estado, para arrastrar y ver la carga de la semana.
- **Calendario** por fecha límite.
- **Análisis** (pivot): resultados por semana, con monto.

### 4.4 Crear un seguimiento a mano

Desde el botón **Nuevo** del menú, desde la ficha del cliente (botón "Televentas") o desde la Matriz de Control con el botón de teléfono en la fila del cliente.

---

## 5. Matriz de Control (gerencia)

**Menú:** Ruteros › Matriz de Control

Es la matriz comercial del Excel, una fila por cliente y por mes. Se recalcula todas las noches; el botón **Recalcular período** la actualiza al momento. Por defecto muestra el mes actual.

### 5.1 Columnas

**Datos del cliente:** ID, nombre comercial, razón social, ruta, agente asignado, teléfono, plazo, lista de precio, fecha de última factura, días sin facturar, frecuencia de visita.

**Bloque agente:** última visita del mes (fecha programada y realizada, resultado, monto, motivo, próxima acción y fecha, comentario, requiere televentas).

**Bloque televentas:** último seguimiento realizado en el mes (fecha, canal, resultado, monto, próxima acción y fecha, comentario) y si hay un pendiente abierto.

**Columnas calculadas:**

| Columna | Cómo se calcula |
|---|---|
| Estado de atención | *Visitado* si hubo visita real en el mes; *Solo televentas* si solo hubo contacto de Natalia; *Pendiente visita* si tocaba visita y no se hizo; *Sin gestión* si no se esperaba nada y no hubo nada |
| Días sin facturar | Días entre la última factura y la fecha de corte |
| Efectividad visita | 100 % venta facturada · 50 % pedido pendiente o cotización · 0 % resto |
| Efectividad televentas | 100 % venta recuperada · 50 % pedido pendiente o cotización · 0 % resto |
| Cliente desatendido | Sin visita y sin contacto de televentas en el mes, cuando sí se esperaba alguno según la frecuencia |
| Responsable próximo paso | *Agente / Televentas* si está desatendido; *Agente* si la acción del agente ya venció; *Televentas* si la de Natalia venció; *Sin acción vencida* |
| Alerta gerencial | En este orden: **CLIENTE SIN ATENCIÓN** → **Más de N días sin facturar** → **Seguimiento vencido** → **OK** |

Las filas se colorean: rojo sin atención, naranja seguimiento vencido, azul más de N días sin facturar.

### 5.2 Filtros y agrupaciones

Filtros por alerta (sin atención, vencido, más de N días, OK), por estado de atención, por responsable pendiente y "registros sin comentario". Agrupar por ruta, agente, estado, alerta o resultado de visita.

### 5.3 Tablero de indicadores

La vista **Pivote** de la matriz reproduce el tablero del Excel. Con filas por ruta o agente y las medidas:

Clientes · Visitados · Solo televentas · Sin atención · Ventas por visita · Ventas recuperadas · Seguimientos vencidos · Más de N días sin facturar · Monto ventas por visita · Monto ventas televentas.

Los porcentajes (cobertura, atención total, conversión, recuperación) se leen dividiendo esas columnas. La vista **Gráfico** muestra la cobertura por ruta apilada por estado de atención.

### 5.4 Resumen semanal en Discuss

Cada lunes a las 6:30 se publica en el canal **Control de Visitas y Rutas** una tabla con los 20 indicadores del mes y los primeros 15 clientes "sin atención" y "seguimiento vencido" por agente. Para recibirlo hay que unirse al canal en Discuss.

### 5.5 Desde la fila de un cliente

- Botón de marcador: abre la visita del mes.
- Botón de teléfono: abre el seguimiento pendiente o crea uno nuevo.
- Doble clic: ficha completa de la línea.

---

## 6. Ficha del cliente

En cada cliente (Contactos) aparece la pestaña **Control de visitas** con:

- **Tipo de atención**: Ruta (visita presencial), Televentas u Oficina. Viene de la ruta, pero se puede cambiar por cliente.
- **Frecuencia de visita**: Semanal, Quincenal, Mensual, Bimensual o Sin visita programada. Viene de la ruta; cambiarla aquí solo afecta a este cliente (por ejemplo, un cliente bimensual dentro de una ruta mensual).
- **Última visita**, **Próxima visita esperada** (última + días de la frecuencia) y **Último contacto televentas**.

Botones **Visitas** y **Televentas** para ver el historial del cliente.

---

## 7. Configuración (gerencia)

### 7.1 Catálogos de visitas

Ruteros › Configuración › Catálogos de visitas. Listas editables agrupadas por tipo:

- Motivos sin venta (16)
- Próximas acciones (14)
- Comentarios predeterminados del agente (20)
- Comentarios predeterminados de televentas (20)

Se puede cambiar el texto, el orden, agregar filas o archivar las que ya no se usen. No borrar ni cambiar el **código** de las que tienen lógica: *Transferir seguimiento a Natalia* y *Cerrar seguimiento*.

### 7.2 Rutas y frecuencias

Ruteros › Configuración › Rutas y frecuencias. Por cada ruta se define el **tipo de atención** y la **frecuencia de visita** que heredan sus clientes. Hoy: TELEVENTAS es de tipo televentas, OFICINA y CORPORATIVO son de oficina, Inactivos sin visita, y el resto rutas mensuales.

### 7.3 Ajustes

Ventas › Ajustes › bloque **Control de visitas y televentas**:

- **Responsable de televentas**: usuario al que se asignan los pendientes y sus actividades (Natalia).
- **Días sin facturar para alerta**: umbral de la alerta "Más de N días sin facturar" (90 por defecto).

### 7.4 Procesos automáticos

| Proceso | Cuándo | Qué hace |
|---|---|---|
| Generar pendientes de televentas | Domingo 6:00 | Crea los pendientes de la semana. **Desactivado al inicio**; gerencia lo activa en Ajustes › Técnico › Acciones planificadas cuando decida arrancar. |
| Recalcular matriz | Diario 2:00 | Regenera el mes actual (y el anterior hasta el día 5). |
| Resumen gerencial | Lunes 6:30 | Publica los indicadores en Discuss. |

---

## 8. Preguntas frecuentes

**¿Por qué un cliente sale "sin atención" si sí lo visitaron?**
Porque la visita no llegó a Odoo (la app no la envió) o llegó con resultado *No visitado* o *Visita reprogramada*, que no cuentan como visita real. Revisar en Ruteros › Visitas.

**¿Por qué la matriz tiene más clientes que el Excel?**
Incluye todos los clientes activos con ventas, sin excluir a los que también son proveedores ni a los que no tienen ruta. Los clientes sin ruta salen con ruta vacía; conviene asignársela.

**¿Cómo evito que a un cliente se le exija visita?**
En su ficha, pestaña Control de visitas, poner frecuencia *Sin visita programada* o tipo *Televentas*.

**No me deja marcar un seguimiento como realizado.**
Falta alguno de: fecha de contacto, canal, resultado o comentario. El mensaje de error indica cuál.

**¿Qué pasa si el agente no elige próxima acción?**
La visita queda sin acción pendiente y el cliente no genera "seguimiento vencido" para el agente. Natalia lo verá solo si la frecuencia de visita vence sin nueva visita.

**¿Dónde veo lo que me toca hoy?**
En el reloj de actividades de la barra superior, o en Ruteros › Seguimiento Televentas con el filtro "Mis pendientes" y "Vencidos".
