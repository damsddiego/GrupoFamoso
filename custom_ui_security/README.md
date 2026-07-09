# Custom UI Security

## Descripción

Módulo profesional para controlar la visibilidad de elementos de interfaz en Odoo 18 según grupos de usuario.

### Fase 1 - Funcionalidad Actual ✅

- **Ocultar el costo de producto** (`standard_price`) para usuarios no autorizados
- Grupo de seguridad: `Puede ver costos de producto`
- Afecta a:
  - `product.template` (formulario, lista, búsqueda)
  - `product.product` (formulario, lista, búsqueda, variantes)

### Fase 2 - Preparación Futura 🚧

El módulo está arquitectónicamente preparado para soportar:

- ✅ Modelo `ui.security.rule` para reglas configurables
- ✅ Ocultar/mostrar campos dinámicamente
- ✅ Ocultar botones por grupo
- ✅ Campos de solo lectura condicionales
- ✅ Ocultar pestañas/páginas completas
- ✅ Ocultar columnas en vistas tree
- ✅ Motor dinámico de aplicación de reglas

---

## Instalación

### 1. Copiar el módulo

```bash
cp -r custom_ui_security /opt/odoo18/odoo18-custom-addons/
chown -R odoo18:odoo18 /opt/odoo18/odoo18-custom-addons/custom_ui_security
```

### 2. Reiniciar Odoo

```bash
sudo systemctl restart odoo18
```

### 3. Actualizar lista de aplicaciones

En Odoo:
- Ir a **Aplicaciones**
- Activar modo desarrollador
- Click en **Actualizar lista de aplicaciones**
- Buscar "Custom UI Security"
- Instalar

---

## Uso

### Fase 1: Controlar visibilidad de costos

#### 1. Asignar grupo a usuarios

Ir a: **Configuración → Usuarios y Compañías → Usuarios**

Para cada usuario que **debe ver costos**:
- Editar usuario
- Pestaña **Otros**
- En sección **UI Security**, marcar:
  - ☑ **Puede ver costos de producto**

#### 2. Verificar

- Usuarios **con el grupo**: verán el campo "Costo" en productos
- Usuarios **sin el grupo**: NO verán el campo "Costo" en ninguna vista

---

## Arquitectura Técnica

### Estructura del Módulo

```
custom_ui_security/
├── models/
│   └── ui_security_rule.py       # Modelo placeholder para Fase 2
├── views/
│   ├── product_template_views.xml # Herencia XML para ocultar costos
│   ├── product_product_views.xml  # Herencia XML para variantes
│   └── ui_security_rule_views.xml # Interfaz de configuración (Fase 2)
├── security/
│   ├── security.xml               # Grupos de seguridad
│   └── ir.model.access.csv        # Permisos de acceso
```

### Enfoque Técnico

#### Fase 1: Herencia XML pura

- Uso del atributo `groups` en elementos XML
- XPath dirigidos y no invasivos
- Sin código Python personalizado
- Performance óptima

```xml
<xpath expr="//field[@name='standard_price']" position="attributes">
    <attribute name="groups">custom_ui_security.group_view_product_cost</attribute>
</xpath>
```

#### Fase 2: Motor dinámico (preparado)

- Override de `fields_view_get`
- Procesamiento dinámico de reglas
- Cache para optimizar performance
- Configuración desde interfaz

---

## Extensión - Fase 2

### Activar el motor dinámico

#### 1. Descomentar el modelo

En [models/__init__.py](models/__init__.py):

```python
from . import ui_security_rule  # ← Descomentar
```

#### 2. Descomentar la vista

En [__manifest__.py](__manifest__.py):

```python
'data': [
    # ...
    'views/ui_security_rule_views.xml',  # ← Descomentar
],
```

#### 3. Actualizar el módulo

```bash
odoo-bin -u custom_ui_security -d tu_base_de_datos
```

#### 4. Implementar el hook

Crear un mixin para aplicar reglas dinámicamente. Ver documentación completa en [models/ui_security_rule.py:270-320](models/ui_security_rule.py#L270-L320)

### Casos de uso comunes

#### Ocultar un botón

```python
# Crear regla desde interfaz o por código:
{
    'name': 'Ocultar botón Confirmar en Pedidos',
    'model_id': self.env.ref('sale.model_sale_order').id,
    'target_type': 'button',
    'target_name': 'action_confirm',
    'rule_type': 'hide',
    'view_types': 'form',
    'group_mode': 'show_only_for',
    'group_ids': [(6, 0, [self.env.ref('sales_team.group_sale_manager').id])]
}
```

#### Campo de solo lectura

```python
{
    'name': 'Precio de venta readonly para vendedores',
    'model_id': self.env.ref('product.model_product_template').id,
    'target_type': 'field',
    'target_name': 'list_price',
    'rule_type': 'readonly',
    'view_types': 'form',
    'group_mode': 'hide_for',
    'group_ids': [(6, 0, [self.env.ref('sales_team.group_sale_manager').id])]
}
```

#### Ocultar pestaña completa

```python
{
    'name': 'Ocultar pestaña Contabilidad',
    'model_id': self.env.ref('sale.model_sale_order').id,
    'target_type': 'page',
    'target_name': 'invoice_tab',  # name de la <page>
    'rule_type': 'hide',
    'view_types': 'form',
    'group_mode': 'show_only_for',
    'group_ids': [(6, 0, [self.env.ref('account.group_account_user').id])]
}
```

---

## Limitaciones y Consideraciones

### Limitaciones de XML puro (Fase 1)

✅ **Funciona perfectamente para:**
- Campos individuales
- Elementos con nombre único
- Vistas estándar bien identificadas

⚠️ **Limitaciones:**
- No puede ocultar elementos sin `name` o `id`
- No puede aplicar lógica compleja (ej: "ocultar si campo X tiene valor Y")
- Requiere herencia manual para cada vista

### Ventajas del motor dinámico (Fase 2)

✅ **Permite:**
- Configuración desde interfaz, sin código
- Aplicación automática a vistas dinámicas
- Lógica condicional avanzada
- Mantenimiento centralizado

⚠️ **Consideraciones:**
- Requiere procesamiento adicional en cada carga de vista
- Necesita cache para optimizar performance
- Puede requerir JavaScript para casos complejos

---

## Testing

### Pruebas manuales

1. **Sin el grupo:**
   - Login con usuario sin `group_view_product_cost`
   - Ir a Productos
   - Verificar que NO aparece el campo "Costo"

2. **Con el grupo:**
   - Login con usuario con `group_view_product_cost`
   - Ir a Productos
   - Verificar que SÍ aparece el campo "Costo"

### Pruebas automatizadas (futuro)

Ver ejemplo en comentarios de código en [models/ui_security_rule.py](models/ui_security_rule.py)

---

## Soporte y Contribución

- **Documentación:** Ver comentarios en código
- **Issues:** Reportar problemas en el sistema de tickets interno
- **Mejoras:** Contactar al equipo de desarrollo

---

## Licencia

LGPL-3

---

## Autor

**Tu Empresa** - Equipo de Desarrollo Odoo

---

## Próximos Pasos Recomendados

1. **Instalar y probar** en entorno de desarrollo
2. **Validar** con usuarios reales
3. **Decidir** si necesitas activar Fase 2
4. **Extender** según necesidades (botones, pestañas, etc.)
5. **Integrar** con módulos propios de tu empresa

---

## Notas Importantes de Seguridad

⚠️ **IMPORTANTE:** Ocultar elementos de UI **NO es seguridad real.**

Un usuario técnico puede:
- Llamar a métodos XML-RPC/JSON-RPC directamente
- Modificar el XML de la vista en el navegador (DevTools)
- Usar `read()` para acceder a campos ocultos

**Para seguridad real, SIEMPRE combinar con:**
- **Record rules** (`ir.rule`)
- **Permisos de campo** (`ir.model.fields.access` en Odoo 15+)
- **Decoradores** `@api.constrains` en métodos

**Ejemplo:**

```python
# Seguridad de UI (Fase 1/2)
# views/product_views.xml
<field name="standard_price" groups="custom_ui_security.group_view_product_cost"/>

# Seguridad de datos (OBLIGATORIO)
# models/product_template.py
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.constrains('standard_price')
    def _check_can_write_cost(self):
        if not self.env.user.has_group('custom_ui_security.group_view_product_cost'):
            raise ValidationError("No tiene permisos para modificar el costo.")
```

---

## Historial de Versiones

### 18.0.1.0.0 (2026-04-15)
- ✅ Implementación Fase 1: Ocultar costos de producto
- ✅ Preparación arquitectónica para Fase 2
- ✅ Modelo `ui.security.rule` (placeholder)
- ✅ Documentación completa
