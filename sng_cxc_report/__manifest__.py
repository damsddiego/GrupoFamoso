# -*- coding: utf-8 -*-
{
    "name": "SNG CxC Report",
    "version": "18.0.1.1.0",
    "category": "Accounting/Accounting",
    "summary": "Reporte de cuentas por cobrar por cliente con antiguedad y exportacion a Excel",
    "author": "SNG",
    "license": "LGPL-3",
    "depends": [
        "account",
        "sale",
        "web",
        "customer_sequence",
        "sng_custom_name_partner",
        "sales_commission_omax",
        "sng_sales_routes",
        "spreadsheet_dashboard",
        "regalarte_customer_metrics",
        "sale_stock_sng",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sng_cxc_report_views.xml",
        "views/sng_cxc_report_wizard_views.xml",
        "views/sng_cxc_report_menus.xml",
        "data/cxc_dashboard.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sng_cxc_report/static/src/js/action_manager.js",
        ],
    },
    "installable": True,
    "application": False,
}
