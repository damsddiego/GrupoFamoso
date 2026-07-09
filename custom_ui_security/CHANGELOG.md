# Changelog - Custom UI Security

Todos los cambios notables de este módulo se documentarán en este archivo.

---

## [18.0.1.0.2] - 2026-04-15

### 🐛 Corregido

- **Error XPath en vistas:** Los archivos XML intentaban modificar campos `standard_price` en vistas donde no existen (tree/search)
  - **Solución:** Eliminadas herencias innecesarias de vistas tree/search de `product.template`
  - **Solución:** Eliminada herencia innecesaria de vista search de `product.product`
  - Solo se mantienen herencias para vistas form (formulario) y tree de `product.product` donde el campo realmente existe

### 📝 Archivos afectados

- `views/product_template_views.xml` - Reducido a 2 herencias (form y variant)
- `views/product_product_views.xml` - Reducido a 2 herencias (form y tree)

---

## [18.0.1.0.1] - 2026-04-15

### 🐛 Corregido

- **Error en instalación inicial:** El archivo `ir.model.access.csv` hacía referencia al modelo `ui_security_rule` que no está activo en Fase 1
  - **Solución:** El archivo `ir.model.access.csv` ahora solo contiene el encabezado
  - Los permisos de acceso para Fase 2 se movieron a `security/ir.model.access.fase2.csv`
  - Este archivo debe descomentarse en `__manifest__.py` cuando se active la Fase 2

### 📝 Documentación

- Actualizado `__manifest__.py` con comentarios explicativos sobre el CSV vacío
- Actualizado `FASE2_IMPLEMENTACION.md` con instrucciones sobre activación de permisos
- Agregado este archivo `CHANGELOG.md` para documentar cambios

---

## [18.0.1.0.0] - 2026-04-15

### ✨ Nuevo - Lanzamiento Inicial

#### Fase 1 - Funcionalidad Actual

- ✅ Grupo de seguridad: `group_view_product_cost` ("Puede ver costos de producto")
- ✅ Herencia XML para ocultar campo `standard_price` en:
  - `product.template` (formulario, lista, búsqueda)
  - `product.product` (formulario, lista, búsqueda, variantes)
- ✅ Asignación automática del grupo a administradores
- ✅ Implementación basada en herencia XML pura (atributo `groups`)

#### Fase 2 - Arquitectura Preparada

- ✅ Modelo completo `ui.security.rule` (comentado, listo para activar)
- ✅ Vistas completas de configuración (comentadas)
- ✅ Estructura preparada para motor dinámico de reglas
- ✅ Soporte futuro para:
  - Ocultar campos dinámicamente
  - Ocultar botones por grupo
  - Campos readonly condicionales
  - Ocultar pestañas/páginas
  - Ocultar columnas en listas

#### Documentación

- ✅ `README.md` completo (7,900+ caracteres)
- ✅ `INSTALL.md` con guía paso a paso
- ✅ `FASE2_IMPLEMENTACION.md` con guía técnica detallada
- ✅ Comentarios explicativos en todo el código

#### Archivos del Módulo

- `__init__.py` - Importaciones principales
- `__manifest__.py` - Configuración del módulo
- `models/ui_security_rule.py` - Modelo Fase 2 (300+ líneas)
- `views/product_template_views.xml` - Herencias para product.template
- `views/product_product_views.xml` - Herencias para product.product
- `views/ui_security_rule_views.xml` - Interfaz Fase 2 (comentada)
- `security/security.xml` - Grupos de seguridad
- `security/ir.model.access.csv` - Permisos (vacío en Fase 1)
- `security/ir.model.access.fase2.csv` - Permisos para Fase 2
- `data/ui_security_demo.xml` - Datos demo (opcional)

---

## Formato del Changelog

Este archivo sigue el formato de [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

### Tipos de cambios

- **✨ Nuevo** - Nuevas funcionalidades
- **🔄 Cambiado** - Cambios en funcionalidad existente
- **❌ Deprecado** - Funcionalidad que será removida
- **🗑️ Removido** - Funcionalidad removida
- **🐛 Corregido** - Corrección de bugs
- **🔒 Seguridad** - Correcciones de seguridad
- **📝 Documentación** - Cambios en documentación

---

## Notas de Migración

### De Fase 1 a Fase 2

Cuando decidas activar Fase 2:

1. Descomentar en `models/__init__.py`:
   ```python
   from . import ui_security_rule
   ```

2. Descomentar en `__manifest__.py`:
   ```python
   'views/ui_security_rule_views.xml',
   'security/ir.model.access.fase2.csv',
   ```

3. Actualizar módulo:
   ```bash
   odoo-bin -u custom_ui_security -d tu_bd
   ```

4. Verificar que el menú "UI Security" aparece en Odoo

5. Opcionalmente, crear reglas dinámicas equivalentes a las herencias XML estáticas

Ver guía completa en: `FASE2_IMPLEMENTACION.md`

---

**Mantenido por:** Tu Empresa - Equipo de Desarrollo Odoo
