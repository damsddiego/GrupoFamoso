# -*- coding: utf-8 -*-
{
    "name": "Dashboard de Inventario por Categorias",
    "version": "18.0.1.0.0",
    "category": "Inventory/Reporting",
    "summary": "Reporte XLSX de inventario por categorias con dashboard final.",
    "description": """
Genera un archivo Excel con:
- Una hoja por categoria
- Analisis mensual, semanal o ambos
- Inventario inicial y final
- Llegadas, ventas, cobertura y compra sugerida
- Dashboard final alimentado desde las hojas de categorias
    """,
    "author": "SNG",
    "website": "https://www.sngcloud.com",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "custom_ui_security",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_category_views.xml",
        "views/category_inventory_dashboard_wizard_views.xml",
    ],
    "external_dependencies": {
        "python": ["xlsxwriter"],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
