# -*- coding: utf-8 -*-
{
    'name': 'Reporte de Artículos sin Imagen por Compañía',
    'version': '18.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Listado de productos activos sin imagen principal, con código y descripción, agrupado por compañía',
    'description': """
Reporte de Artículos sin Imagen
================================
Muestra los productos (plantillas) activos que no tienen imagen principal
cargada (image_1920), con:
- Código interno
- Descripción
- Categoría, tipo, precio de venta
- Compañía

Características:
- SQL VIEW para máxima eficiencia (siempre actualizado, sin recálculos)
- Vistas List y Pivot, agrupado por compañía por defecto
- Wizard de filtros (compañías, categoría, tipo, solo vendibles/comprables)
- Multi-compañía compatible (los productos compartidos se ven en todas)
- Exportable a Excel con el botón estándar de Odoo
- Botón para abrir el producto y cargarle la imagen
    """,
    'author': 'SNG',
    'depends': [
        'product',
        'stock',
        'sales_team',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/sng_product_no_image_views.xml',
        'views/sng_product_no_image_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
