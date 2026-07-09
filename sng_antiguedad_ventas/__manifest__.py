# -*- coding: utf-8 -*-
{
    "name": "SNG Antigüedad de Ventas",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Reporte de antigüedad de cartera por cliente con tramos de 30 días y exportación a Excel",
    "author": "SNG",
    "license": "LGPL-3",
    "depends": [
        "account",
        "web",
        "customer_sequence",
        "sng_custom_name_partner",
        "sales_commission_omax",
        "sale_account_manager_customer_credit_limit_approval",
        "sng_sales_routes",
    ],
    "data": [
        "security/sng_antiguedad_ventas_security.xml",
        "security/ir.model.access.csv",
        "wizard/sng_antiguedad_ventas_wizard_views.xml",
        "views/sng_antiguedad_ventas_views.xml",
        "views/sng_antiguedad_ventas_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sng_antiguedad_ventas/static/src/js/action_manager.js",
        ],
    },
    "installable": True,
    "application": False,
}
