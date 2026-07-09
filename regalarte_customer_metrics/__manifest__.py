# -*- coding: utf-8 -*-
{
    "name": "Regalarte Customer Metrics",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "summary": "Indicadores comerciales y financieros en la ficha del cliente",
    "author": "SNG",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "account",
        "sales_commission_omax",
        "web",
    ],
    "data": [
        "data/ir_actions_server.xml",
        "data/ir_cron.xml",
        "security/ir.model.access.csv",
        "security/regalarte_customer_metrics_security.xml",
        "views/customer_metric_views.xml",
        "views/res_partner_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "regalarte_customer_metrics/static/src/js/action_manager.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
