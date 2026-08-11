{
    "name": "SNG Bloqueo de Impuestos en Ventas y Facturas",
    "version": "18.0.1.1.0",
    "category": "Accounting/Accounting",
    "summary": "Restringe la edicion de impuestos al administrador de Ajustes",
    "author": "SNG",
    "website": "https://www.sngcloud.com",
    "license": "LGPL-3",
    "depends": ["sale_management", "account"],
    "data": [
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
