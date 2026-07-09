# -*- coding: utf-8 -*-
{
    "name": "Reporte de Sugerido de Compras",
    "version": "18.0.1.0.0",
    "category": "Inventory/Reporting",
    "summary": "Reporte de inventario, ventas entregadas, demanda y sugerido de compras.",
    "description": """
Genera un reporte en pantalla y descargable a Excel con:
- Codigo y nombre de producto
- Cantidad real disponible sin reservas
- Total de venta segun cantidades entregadas
- Promedio mensual por meses historicos configurables
- Meses de abastecimiento
- Demanda segun meses de cobertura configurables
- Sugerido de compras
    """,
    "author": "SNG",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "sale_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_suggestion_report_views.xml",
    ],
    "external_dependencies": {
        "python": ["xlsxwriter"],
    },
    "installable": True,
    "application": False,
}
