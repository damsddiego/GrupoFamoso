# SNG Bloqueo de Impuestos en Ventas y Facturas

Restringe la modificacion manual de los impuestos en lineas de pedidos de
venta y facturas al grupo **Ajustes / Administrador** (`base.group_system`).

El bloqueo se aplica tanto en las vistas como en el servidor. Los impuestos
calculados automaticamente al seleccionar un producto y los impuestos creados
durante la importacion de documentos electronicos siguen funcionando.

El modulo trabaja sobre los modelos estandar `sale.order.line` y
`account.move.line`, y depende de `cr_electronic_invoice` para leer el
campo `tipo_documento` de la factura.

## Reglas aplicadas

- **Cotizaciones / pedidos de venta**: cualquier usuario puede **quitar**
  el impuesto de una linea (venta que terminara en documento electronico
  desactivado). Asignar un impuesto **distinto** al calculado por el
  producto sigue siendo exclusivo de `base.group_system`; el impuesto del
  producto se asigna solo al seleccionar el producto. Los pedidos se pueden
  confirmar sin impuesto: el control se aplica al facturar.
- **Editar impuestos en lineas de factura** (`write`): solo
  `base.group_system`. La vista muestra el campo como solo lectura y el
  servidor rechaza el cambio con `AccessError`.
- **Excepcion — documentos electronicos desactivados**: si la factura tiene
  `tipo_documento = disabled` ("Electronic Documents Disabled"), cualquier
  usuario puede editar o quitar los impuestos de sus lineas. Esas facturas
  no se reportan a Hacienda, por lo que el bloqueo no aplica.
- **Confirmar (validar) facturas de cliente** (`action_post`, facturas y
  notas de credito): si el tipo de documento **no** es "Documentos
  electronicos desactivados" (y la compania no tiene la FE deshabilitada),
  todas las lineas de producto deben tener impuesto; si alguna no lo tiene
  se rechaza con `UserError` (aplica a todos los usuarios, incluidos
  administradores). Se excluyen las lineas de la categoria "Otros Cargos" y
  el producto "IVA Devuelto", que van sin impuesto por diseno de la FE.
- **Crear lineas de factura** no se restringe en el servidor: la
  importacion de documentos electronicos (`cr_electronic_invoice`) crea
  lineas con `tax_ids` explicitos (incluyendo vacios en "Otros Cargos") y
  debe seguir funcionando. La vista mantiene el campo readonly.
