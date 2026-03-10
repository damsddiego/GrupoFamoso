# CR Auto Discount Fields

## Descripción

Este módulo automáticamente llena los campos `discount_code_id` y `discount_note` en las líneas de factura cuando se aplica un descuento, para cumplir con los requisitos de facturación electrónica de Costa Rica.

## Funcionalidad

Cuando una línea de factura tiene un descuento mayor a 0%, el módulo automáticamente:
- Asigna un código de descuento configurable al campo `discount_code_id`
- Llena el campo `discount_note` con un texto configurable

Esto funciona tanto:
- Al crear facturas desde órdenes de venta con descuentos
- Al editar manualmente líneas de factura con descuentos
- Al cambiar el porcentaje de descuento en una línea existente

## Instalación

1. El módulo ya está ubicado en: `/opt/odoo18/l10n_cr/l10n_cr/sng_auto_discount_fields/`

2. Reinicia el servidor Odoo:
   ```bash
   sudo systemctl restart odoo18
   ```

3. Actualiza la lista de aplicaciones en Odoo:
   - Ve a **Aplicaciones**
   - Haz clic en **"Actualizar lista de aplicaciones"**

4. Busca e instala/actualiza el módulo:
   - Busca **"CR Auto Discount Fields"**
   - Haz clic en **"Instalar"** o **"Actualizar"** si ya está instalado

## Configuración

Una vez instalado el módulo, configúralo desde:

**Contabilidad → Configuración → Ajustes**

Busca la sección **"Configuración de Descuentos Automáticos"** donde podrás:

1. **Activar/Desactivar** el llenado automático de campos de descuento
2. **Seleccionar el Código de Descuento** que se aplicará automáticamente (de la lista de códigos de descuento ya cargados en el sistema)
3. **Definir la Nota de Descuento** (texto personalizado, ej: "Promo", "Descuento comercial", etc.)

### Captura de pantalla de configuración:
```
☑ Activar Auto-llenado de Campos de Descuento
  Activa el llenado automático de campos de descuento en facturas

Código de Descuento: [Seleccionar de la lista] ▼
  Seleccione el código de descuento que se aplicará automáticamente

Nota de Descuento: [Promo                    ]
  Texto que se mostrará en la nota de descuento
```

## Dependencias

- sale
- account
- cr_electronic_invoice

## Notas Importantes

- El módulo **NO sobrescribe** valores si ya están manualmente asignados
- Si el descuento se elimina o se pone en 0%, los campos se limpian automáticamente
- El código de descuento '07' (Descuento Comercial) se crea automáticamente al instalar el módulo
- Puedes usar **cualquier código de descuento** existente en tu sistema mediante la configuración
- La configuración es **global** para toda la compañía
- Puedes activar/desactivar la funcionalidad sin desinstalar el módulo
