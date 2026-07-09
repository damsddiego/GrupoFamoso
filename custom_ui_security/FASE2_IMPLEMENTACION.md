# Guía de Implementación - Fase 2

## Motor Dinámico de Reglas de UI Security

Esta guía describe cómo activar e implementar el motor dinámico de reglas de UI Security (Fase 2).

---

## 📋 Índice

1. [Activación del Modelo](#activación-del-modelo)
2. [Implementación del Motor](#implementación-del-motor)
3. [Casos de Uso Avanzados](#casos-de-uso-avanzados)
4. [Optimización y Performance](#optimización-y-performance)
5. [Limitaciones y Soluciones](#limitaciones-y-soluciones)

---

## 1. Activación del Modelo

### Paso 1.1: Descomentar importación

Editar [models/__init__.py](models/__init__.py):

```python
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# FASE 2: Descomentar cuando se active el motor dinámico
from . import ui_security_rule  # ← DESCOMENTAR ESTA LÍNEA
```

### Paso 1.2: Descomentar vistas y permisos en manifest

Editar [__manifest__.py](__manifest__.py):

```python
'data': [
    # Seguridad
    'security/security.xml',
    'security/ir.model.access.csv',

    # Vistas de productos (Fase 1)
    'views/product_template_views.xml',
    'views/product_product_views.xml',

    # Vistas de configuración (Fase 2 - descomentar cuando se active)
    'views/ui_security_rule_views.xml',  # ← DESCOMENTAR ESTA LÍNEA

    # Permisos de acceso para Fase 2 (descomentar cuando se active el modelo)
    'security/ir.model.access.fase2.csv',  # ← DESCOMENTAR ESTA LÍNEA

    # Datos de ejemplo (opcional)
    # 'data/ui_security_demo.xml',
],
```

**Nota importante:** El archivo `ir.model.access.csv` está vacío en Fase 1 (solo contiene encabezado). Los permisos reales para el modelo `ui.security.rule` están en `ir.model.access.fase2.csv` y deben descomentarse junto con la vista.

### Paso 1.3: Actualizar el módulo

```bash
sudo -u odoo18 /opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo/odoo-bin \
  -d tu_base_de_datos \
  -u custom_ui_security \
  --stop-after-init
```

### Paso 1.4: Verificar

En Odoo:
1. Ir a **Aplicaciones**
2. Buscar "UI Security"
3. Debe aparecer un nuevo menú en la aplicación

---

## 2. Implementación del Motor

### 2.1: Crear el Mixin Base

Crear archivo `models/ui_security_mixin.py`:

```python
# -*- coding: utf-8 -*-
from odoo import models, api
from lxml import etree


class UiSecurityMixin(models.AbstractModel):
    """
    Mixin para aplicar reglas de UI Security dinámicamente.

    Se aplicará automáticamente a todos los modelos que tengan
    reglas de seguridad configuradas.
    """

    _name = 'ui.security.mixin'
    _description = 'Mixin para UI Security'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """
        Override de fields_view_get para aplicar reglas de UI Security.
        """
        # 1. Obtener vista base (incluye herencias estáticas XML)
        result = super().fields_view_get(view_id, view_type, toolbar, submenu)

        # 2. Buscar reglas aplicables
        rules = self._get_ui_security_rules(view_type)

        if not rules:
            return result

        # 3. Aplicar reglas a la vista
        arch = etree.fromstring(result['arch'])
        arch = self._apply_ui_security_rules(arch, rules, view_type)
        result['arch'] = etree.tostring(arch, encoding='unicode')

        return result

    def _get_ui_security_rules(self, view_type):
        """
        Obtiene las reglas aplicables al modelo y tipo de vista actual.

        Args:
            view_type (str): Tipo de vista (form, tree, etc.)

        Returns:
            recordset: Reglas aplicables
        """
        UiSecurityRule = self.env['ui.security.rule'].sudo()

        domain = [
            ('active', '=', True),
            ('model_name', '=', self._name),
            '|',
            ('view_types', '=', 'all'),
            ('view_types', '=', view_type),
        ]

        return UiSecurityRule.search(domain, order='sequence')

    def _apply_ui_security_rules(self, arch, rules, view_type):
        """
        Aplica las reglas de seguridad a la arquitectura de la vista.

        Args:
            arch (etree.Element): Arquitectura XML de la vista
            rules (recordset): Reglas a aplicar
            view_type (str): Tipo de vista

        Returns:
            etree.Element: Arquitectura modificada
        """
        for rule in rules:
            # Verificar si la regla aplica al usuario actual
            if not rule._applies_to_current_user():
                continue

            # Aplicar según tipo de elemento
            if rule.target_type == 'field':
                arch = self._apply_field_rule(arch, rule)
            elif rule.target_type == 'button':
                arch = self._apply_button_rule(arch, rule)
            elif rule.target_type == 'page':
                arch = self._apply_page_rule(arch, rule)
            elif rule.target_type == 'group':
                arch = self._apply_group_rule(arch, rule)

        return arch

    def _apply_field_rule(self, arch, rule):
        """Aplica regla a un campo."""
        xpath = f"//field[@name='{rule.target_name}']"
        fields = arch.xpath(xpath)

        for field in fields:
            if rule.rule_type == 'hide':
                # Ocultar completamente
                field.set('invisible', '1')
            elif rule.rule_type == 'readonly':
                # Solo lectura
                field.set('readonly', '1')
            elif rule.rule_type == 'required':
                # Campo requerido
                field.set('required', '1')

        return arch

    def _apply_button_rule(self, arch, rule):
        """Aplica regla a un botón."""
        xpath = f"//button[@name='{rule.target_name}']"
        buttons = arch.xpath(xpath)

        for button in buttons:
            if rule.rule_type == 'hide':
                button.set('invisible', '1')

        return arch

    def _apply_page_rule(self, arch, rule):
        """Aplica regla a una pestaña/página."""
        xpath = f"//page[@name='{rule.target_name}']"
        pages = arch.xpath(xpath)

        # Si no encuentra por name, buscar por string
        if not pages:
            xpath = f"//page[@string='{rule.target_name}']"
            pages = arch.xpath(xpath)

        for page in pages:
            if rule.rule_type == 'hide':
                page.set('invisible', '1')

        return arch

    def _apply_group_rule(self, arch, rule):
        """Aplica regla a un grupo XML."""
        xpath = f"//group[@name='{rule.target_name}']"
        groups = arch.xpath(xpath)

        for group in groups:
            if rule.rule_type == 'hide':
                group.set('invisible', '1')

        return arch
```

### 2.2: Actualizar el modelo ui_security_rule

Agregar método en [models/ui_security_rule.py](models/ui_security_rule.py):

```python
def _applies_to_current_user(self):
    """
    Verifica si la regla aplica al usuario actual.

    Returns:
        bool: True si la regla debe aplicarse, False en caso contrario
    """
    self.ensure_one()

    user_groups = self.env.user.groups_id
    has_group = any(g in self.group_ids for g in user_groups)

    if self.group_mode == 'show_only_for':
        # Mostrar solo si el usuario tiene el grupo
        # Si NO tiene el grupo, ocultar (return True para aplicar regla)
        return not has_group
    else:  # hide_for
        # Ocultar si el usuario tiene el grupo
        return has_group
```

### 2.3: Aplicar el mixin a modelos específicos

**Opción A: Manual (recomendado para producción)**

Crear herederos específicos para cada modelo:

```python
# models/product_template.py
from odoo import models

class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'ui.security.mixin']
```

**Opción B: Automático (más avanzado)**

Aplicar a todos los modelos mediante monkey patch (ver README.md, sección "Integración sin modificar modelos estándar").

### 2.4: Actualizar __init__.py

```python
# models/__init__.py
from . import ui_security_rule
from . import ui_security_mixin
# from . import product_template  # Si usas Opción A
```

---

## 3. Casos de Uso Avanzados

### 3.1: Ocultar botón de confirmación de pedidos

```python
self.env['ui.security.rule'].create({
    'name': 'Ocultar botón Confirmar pedido para vendedores',
    'model_id': self.env.ref('sale.model_sale_order').id,
    'target_type': 'button',
    'target_name': 'action_confirm',
    'rule_type': 'hide',
    'view_types': 'form',
    'group_mode': 'show_only_for',
    'group_ids': [(6, 0, [
        self.env.ref('sales_team.group_sale_manager').id
    ])]
})
```

### 3.2: Campo de solo lectura para vendedores

```python
self.env['ui.security.rule'].create({
    'name': 'Precio de venta readonly para vendedores',
    'model_id': self.env.ref('product.model_product_template').id,
    'target_type': 'field',
    'target_name': 'list_price',
    'rule_type': 'readonly',
    'view_types': 'form',
    'group_mode': 'hide_for',
    'group_ids': [(6, 0, [
        self.env.ref('sales_team.group_sale_manager').id
    ])]
})
```

### 3.3: Ocultar pestaña completa

```python
self.env['ui.security.rule'].create({
    'name': 'Ocultar pestaña de Inventario',
    'model_id': self.env.ref('product.model_product_template').id,
    'target_type': 'page',
    'target_name': 'inventory',
    'rule_type': 'hide',
    'view_types': 'form',
    'group_mode': 'show_only_for',
    'group_ids': [(6, 0, [
        self.env.ref('stock.group_stock_manager').id
    ])]
})
```

---

## 4. Optimización y Performance

### 4.1: Cache de reglas

Agregar cache al método de búsqueda de reglas:

```python
from odoo.tools import ormcache

class UiSecurityMixin(models.AbstractModel):
    # ...

    @ormcache('self.env.uid', 'self._name', 'view_type')
    def _get_ui_security_rules_cached(self, view_type):
        """Versión con cache de _get_ui_security_rules."""
        return self._get_ui_security_rules(view_type)
```

### 4.2: Invalidar cache cuando se modifican reglas

```python
class UiSecurityRule(models.Model):
    # ...

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._invalidate_ui_security_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._invalidate_ui_security_cache()
        return result

    def unlink(self):
        self._invalidate_ui_security_cache()
        return super().unlink()

    def _invalidate_ui_security_cache(self):
        """Invalida el cache de reglas UI."""
        self.env['ui.security.mixin']._get_ui_security_rules_cached.clear_cache(self.env['ui.security.mixin'])
```

---

## 5. Limitaciones y Soluciones

### 5.1: Campos readonly con grupos

**Problema:** El atributo `readonly` no soporta `groups` directamente.

**Solución:** Usar campos computados auxiliares:

```python
# En el modelo objetivo
_can_edit_field = fields.Boolean(
    compute='_compute_can_edit_field',
    store=False
)

@api.depends_context('uid')
def _compute_can_edit_field(self):
    can_edit = self.env.user.has_group('custom_ui_security.group_can_edit')
    for record in self:
        record._can_edit_field = can_edit

# En la vista
<field name="my_field" attrs="{'readonly': [('_can_edit_field', '=', False)]}"/>
<field name="_can_edit_field" invisible="1"/>
```

### 5.2: Elementos sin name o id

**Problema:** No se puede localizar elementos sin atributos identificadores.

**Solución:** Heredar la vista primero para agregar `name`:

```xml
<record id="add_name_to_div" model="ir.ui.view">
    <field name="name">add.name.to.div</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <xpath expr="//div[@class='oe_title']" position="attributes">
            <attribute name="name">title_div</attribute>
        </xpath>
    </field>
</record>
```

### 5.3: Vistas JavaScript (Kanban, Timeline)

**Problema:** Elementos renderizados con QWeb no se pueden modificar con XPath simple.

**Solución:** Requiere JavaScript para modificar templates QWeb o heredar el template completo.

---

## 6. Testing

### 6.1: Test unitario de reglas

```python
from odoo.tests import TransactionCase

class TestUiSecurityRules(TransactionCase):

    def setUp(self):
        super().setUp()
        self.ProductTemplate = self.env['product.template']
        self.UiSecurityRule = self.env['ui.security.rule']

        # Crear grupo de prueba
        self.test_group = self.env['res.groups'].create({
            'name': 'Test Group'
        })

        # Crear usuario de prueba
        self.test_user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'testuser',
            'groups_id': [(6, 0, [self.test_group.id])]
        })

    def test_field_hidden_for_user_without_group(self):
        """Test que el campo se oculta para usuarios sin grupo."""
        # Crear regla
        rule = self.UiSecurityRule.create({
            'name': 'Hide cost',
            'model_id': self.env.ref('product.model_product_template').id,
            'target_type': 'field',
            'target_name': 'standard_price',
            'rule_type': 'hide',
            'view_types': 'form',
            'group_mode': 'show_only_for',
            'group_ids': [(6, 0, [self.env.ref('custom_ui_security.group_view_product_cost').id])]
        })

        # Obtener vista como usuario sin grupo
        view = self.ProductTemplate.with_user(self.test_user).fields_view_get(
            view_type='form'
        )

        # Verificar que el campo tiene invisible="1"
        self.assertIn('invisible="1"', view['arch'])
```

---

## 7. Migración desde Fase 1 a Fase 2

### 7.1: Crear reglas equivalentes a herencias XML

Si quieres reemplazar las herencias XML estáticas con reglas dinámicas:

```python
# Crear regla equivalente a la herencia de product.template
self.env['ui.security.rule'].create({
    'name': 'Ocultar costo de producto (dinámico)',
    'model_id': self.env.ref('product.model_product_template').id,
    'target_type': 'field',
    'target_name': 'standard_price',
    'rule_type': 'hide',
    'view_types': 'all',
    'group_mode': 'show_only_for',
    'group_ids': [(6, 0, [self.env.ref('custom_ui_security.group_view_product_cost').id])]
})

# Repetir para product.product
```

### 7.2: Desactivar herencias XML

Una vez creadas las reglas dinámicas, puedes comentar las herencias XML en el manifest para evitar duplicación.

---

## 8. Roadmap de Mejoras Futuras

### 8.1: Soporte para attrs complejos

Permitir condiciones tipo:

```python
'attrs': "{'invisible': [('state', '!=', 'draft')]}"
```

### 8.2: Reglas basadas en dominio

Aplicar reglas solo si el registro cumple ciertas condiciones:

```python
'domain': "[('state', '=', 'sale')]"
```

### 8.3: Interfaz gráfica para crear reglas

Wizard interactivo que permita:
- Seleccionar modelo
- Ver preview de la vista
- Click en elementos para crear regla

---

## 📚 Recursos Adicionales

- [Documentación Odoo - fields_view_get](https://www.odoo.com/documentation/18.0/developer/reference/backend/views.html)
- [XPath en Odoo](https://www.odoo.com/documentation/18.0/developer/tutorials/getting_started/13_inheritance.html)
- [lxml documentation](https://lxml.de/)

---

**¡Fase 2 lista para implementar!** 🚀
