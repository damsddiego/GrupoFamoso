# -*- coding: utf-8 -*-
{
    'name': 'SNG - Catálogo de Productos por Categoría (PDF)',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Reporting',
    'summary': 'Reporte PDF del inventario de productos agrupados por categoría',
    'description': """
Catálogo de Productos por Categoría
====================================
Genera un reporte PDF profesional del catálogo de productos del inventario,
agrupados por categoría de producto.

Características:
- Filtro por categorías de producto (multiselección)
- Opción de incluir subcategorías recursivamente
- Opción de incluir/excluir productos sin existencia
- Opción de incluir/excluir productos inactivos
- PDF profesional con encabezado de empresa
- Agrupación visual por categoría
- Columnas: Código, Nombre, Cantidad disponible, Precio de venta
    """,
    'author': 'SNG',
    'depends': ['stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/inventory_catalog_wizard_view.xml',
        'report/inventory_catalog_report.xml',
        'report/inventory_catalog_template.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
