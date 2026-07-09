# -*- coding: utf-8 -*-
{
    "name": "Kardex de Inventario",
    "version": "18.0.1.0.0",
    "category": "Inventory",
    "summary": "Reporte Kardex de inventario con saldo acumulado por producto y ubicación.",
    "author": "SNG",
    "license": "LGPL-3",
    "depends": ["base", "stock", "product", "uom"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "wizard/stock_kardex_wizard_views.xml",
        "views/stock_kardex_views.xml",
        "views/product_views.xml",
        "report/stock_kardex_report.xml",
        "report/stock_kardex_report_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
