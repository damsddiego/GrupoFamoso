# SNG Bloqueo de Impuestos en Ventas y Facturas

Restringe la modificacion manual de los impuestos en lineas de pedidos de
venta y facturas al grupo **Ajustes / Administrador** (`base.group_system`).

El bloqueo se aplica tanto en las vistas como en el servidor. Los impuestos
calculados automaticamente al seleccionar un producto y los impuestos creados
durante la importacion de documentos electronicos siguen funcionando.

El modulo trabaja sobre los modelos estandar `sale.order.line` y
`account.move.line`, por lo que tambien cubre las facturas procesadas por
`cr_electronic_invoice` sin modificar ni depender directamente de esa
localizacion.

## Reglas aplicadas

- **Editar impuestos** (`write`) en lineas de venta y de factura: solo
  `base.group_system`. Las vistas muestran el campo como solo lectura
  (lista inline y formulario) y el servidor rechaza el cambio con
  `AccessError`.
- **Crear lineas de venta** con impuestos distintos a los del producto:
  solo `base.group_system`. Un usuario normal puede crear lineas, pero el
  impuesto resultante debe coincidir con el calculado por el producto.
- **Crear lineas de factura** no se restringe en el servidor: la
  importacion de documentos electronicos (`cr_electronic_invoice`) crea
  lineas con `tax_ids` explicitos (incluyendo vacios en "Otros Cargos") y
  debe seguir funcionando. La vista mantiene el campo readonly.
- **Confirmar pedidos/cotizaciones**: ningun pedido se puede confirmar si
  alguna linea de producto no tiene impuesto asignado (aplica a todos los
  usuarios, incluidos administradores). Se excluyen secciones, notas y
  lineas combo.
