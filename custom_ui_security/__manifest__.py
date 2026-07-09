# -*- coding: utf-8 -*-
{
    'name': 'Custom UI Security',
    'version': '18.0.1.0.0',
    'category': 'Administration/Security',
    'summary': 'Control de interfaz basado en grupos de usuario - Framework escalable',
    'description': """
Custom UI Security - Framework Profesional
===========================================

Módulo base para controlar la visibilidad de elementos de interfaz según grupos de usuario.

**Fase 1 - Funcionalidad Actual:**
- Oculta campos de costo a usuarios no autorizados mediante grupo de seguridad
- Grupo de seguridad: "Puede ver costos de producto"
- Afecta a:
  * product.template: campo Cost (standard_price) en formularios y listas
  * product.product: campo Cost (standard_price) en formularios y listas
  * stock.valuation.layer: columnas Unit Cost y Total Value
  * stock.quant: columna Total Value (Average Cost)

**Fase 2 - Preparación Futura:**
El módulo está arquitectónicamente preparado para soportar:
- Reglas configurables por modelo y campo
- Ocultar/mostrar campos, botones, pestañas, columnas
- Campos de solo lectura condicionales por grupo
- Motor dinámico de aplicación de reglas

**Características Técnicas:**
- Herencia XML no invasiva
- Sin modificaciones a lógica contable o inventario
- Compatible con módulos estándar y third-party
- Diseñado para producción y mantenibilidad

**Autor:** Tu Empresa / Equipo de Desarrollo
**Licencia:** LGPL-3
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'stock',
        'stock_account',  # Para ocultar costos en valoración y stock
    ],
    'data': [
        # Seguridad
        'security/security.xml',
        'security/ir.model.access.csv',  # Vacío en Fase 1, solo encabezado

        # Vistas de productos (Fase 1)
        'views/product_template_views.xml',
        'views/product_product_views.xml',

        # Vistas de stock y valoración
        'views/stock_valuation_layer_views.xml',
        'views/stock_quant_views.xml',

        # Vistas de configuración (Fase 2 - descomentar cuando se active)
        # 'views/ui_security_rule_views.xml',

        # Permisos de acceso para Fase 2 (descomentar cuando se active el modelo)
        # 'security/ir.model.access.fase2.csv',

        # Datos de ejemplo (opcional)
        # 'data/ui_security_demo.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': None,
}
