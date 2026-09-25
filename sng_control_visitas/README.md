# SNG Control de Visitas y Rutas

Replica en Odoo la "Matriz Control de visitas y rutas" de gerencia sobre
módulos que ya existen: `sng_ruteros_visitas` (visita GPS desde la app de
ruteros), `sng_sales_routes` (rutas y agente asignado) y `sales_commission_omax`.

## Qué agrega

| Pieza | Dónde |
|---|---|
| Bloque comercial en la visita: resultado, monto, motivo sin venta, próxima acción y fecha, comentario, "requiere televentas" | Ruteros › Visitas |
| Seguimiento de televentas por cliente y semana, con actividad para la responsable | Ruteros › Seguimiento Televentas |
| Matriz mensual por cliente (estado de atención, días sin facturar, efectividad, cliente desatendido, responsable, alerta gerencial) + pivot/gráfico | Ruteros › Matriz de Control |
| Catálogos editables (motivos, próximas acciones, comentarios predeterminados) | Ruteros › Configuración › Catálogos |
| Tipo de atención y frecuencia de visita por ruta, con override por cliente | Ruteros › Configuración › Rutas / ficha del cliente, pestaña "Control de visitas" |
| Responsable de televentas y umbral de días sin facturar | Ventas › Ajustes › Control de visitas y televentas |

## Adaptación Grupo Famoso (multi-compañía)

* Los clientes son compartidos entre compañías: la matriz de cada compañía
  solo incluye a los clientes que le han comprado alguna vez (factura
  publicada en esa compañía) o que son exclusivos de ella (`company_ids`
  del módulo OCA `partner_multi_company` igual a esa compañía; `company_id`
  ahí es un cálculo y no sirve). Un cliente nuevo compartido entra a la
  matriz con su primera factura.
* `assigned_salesperson_id` es un campo por compañía en `sales_commission_omax`:
  el agente de la matriz y del seguimiento de televentas se resuelve con la
  compañía de la línea / del seguimiento.
* `post_init_hook` asigna el grupo de gerencia a `gerencia@grupofsa.net` y
  el responsable de televentas por defecto a `callcenter@grupofsa.net`; si
  no existen se omite y se configura en Ventas › Ajustes › Control de visitas.
* La próxima acción "Transferir seguimiento a televentas" conserva el código
  `transferir_natalia`, que es el gancho que usa la app y la lógica.

## Reglas (de la guía de uso de la matriz)

* Efectividad: 100 % venta facturada / venta recuperada; 50 % pedido pendiente o cotización; 0 % resto.
* Un seguimiento "realizado" exige fecha, canal, resultado y comentario.
* Cliente desatendido: sin visita real y sin contacto de televentas en el mes, cuando se esperaba alguno según la frecuencia.
* Alerta gerencial en cascada: CLIENTE SIN ATENCIÓN → Más de N días sin facturar → Seguimiento vencido → OK.
* Una visita nueva cierra la próxima acción abierta de la visita anterior del mismo cliente; un seguimiento realizado cierra la acción de la visita que lo originó.

## Crons

| Cron | Cuándo | Qué hace |
|---|---|---|
| Generar pendientes de televentas | Domingo 06:00 CR | Crea un pendiente por cliente para la semana: visitas de la semana previa marcadas "requiere televentas" o no realizadas; clientes de ruta con visita vencida según frecuencia; clientes de televentas con contacto vencido. Excluye quien ya tiene pendiente o fue contactado en los últimos 7 días. |
| Recalcular matriz | Diario 02:00 CR | Regenera el mes actual (y el anterior hasta el día 5). |
| Resumen gerencial | Lunes 06:30 CR | Publica los KPIs y los top 15 "sin atención" / "seguimiento vencido" en el canal "Control de Visitas y Rutas". |

## Contrato con la app de ruteros

El `create` de `sng.ruteros.visita` acepta el payload actual sin cambios. Claves
nuevas opcionales:

```
fecha_programada, resultado_comercial, monto_venta, fecha_proxima_accion,
comentario_agente, requiere_seguimiento_televentas,
motivo_sin_venta_id | motivo_sin_venta_codigo,
proxima_accion_id   | proxima_accion_codigo,
comentario_tipo_id  | comentario_tipo_codigo
```

Los `*_codigo` se resuelven contra `sng.visita.catalogo.codigo` (por ejemplo
`transferir_natalia`), para no depender de ids entre entornos. Catálogos:
`search_read('sng.visita.catalogo', [('tipo','=','proxima_accion')], ['id','name','codigo'])`.
Valores de `resultado_comercial`: `fields_get(['resultado_comercial'])`.

## Pruebas

```
python odoo18/odoo-bin -c <conf> -d <db> -u sng_control_visitas --test-enable \
    --test-tags /sng_control_visitas --stop-after-init
```
