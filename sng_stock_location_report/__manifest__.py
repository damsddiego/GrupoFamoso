# -*- coding: utf-8 -*-
{
    "name": "Reporte de Movimientos por Ubicación",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Reporte detallado de movimientos de stock, entradas, salidas y reservas por ubicación con filtros y exportación a Excel",
    "description": """
        Módulo para generar reportes de movimientos de stock por ubicación.
        
        Características:
        - Filtro por almacén (warehouse)
        - Filtro por rango de fechas
        - Visualización de entradas, salidas y reservas
        - Resumen por producto
        - Exportación a Excel (.xlsx)
    """,
    "author": "SNG",
    "license": "LGPL-3",
    "depends": [
        "base",
        "stock",
        "web",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/stock_location_report_views.xml",
        "views/stock_location_report_line_views.xml",
        "views/stock_location_report_warehouse_line_views.xml",
    ],
    "installable": True,
    "application": False,
    "icon": "/stock/static/description/icon.png",
}
