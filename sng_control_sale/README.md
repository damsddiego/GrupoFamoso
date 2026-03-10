# SNG Control Sale

## Descripcion
Este modulo bloquea la confirmacion de ordenes de venta cuando no hay stock
disponible en el almacen de la orden. Solo valida productos almacenables y no
modifica el flujo estandar de Odoo.

## Funcionamiento
1. El usuario crea una cotizacion.
2. Al confirmar, el sistema valida el stock real (qty_available) del almacen.
3. Si no hay stock suficiente, se muestra un error con detalle del producto,
   cantidad solicitada, disponible y almacen.

## Configuracion
Ruta: **Ventas > Configuracion > Ajustes**

- **Bloquear ventas sin stock**: activa la validacion.
- **Permitir excepciones por usuario**: habilita que usuarios con el grupo
  "Permitir confirmar sin stock" puedan confirmar sin bloqueo.
- **Validar solo ciertos almacenes**: si se seleccionan almacenes, solo se
  valida cuando la orden pertenece a esos almacenes.

## Seguridad
Grupo:
- **Permitir confirmar sin stock** (`sng_control_sale.group_allow_negative_stock`)

## Notas tecnicas
- Solo productos almacenables (`type = 'product'`).
- Se convierten cantidades a la UoM del producto antes de comparar.
- Se suman cantidades por producto en la orden antes de validar.
- Respeta compania y almacen de la orden.
- Carga despues de `sale_account_manager_customer_credit_limit_approval` para no perder la validacion de stock.
