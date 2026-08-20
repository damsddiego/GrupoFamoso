{
    "name": "SNG Bloqueo de Impuestos en Ventas y Facturas",
    "version": "18.0.2.0.0",
    "category": "Accounting/Accounting",
    "summary": "Restringe la edicion de impuestos al administrador de Ajustes",
    "author": "SNG",
    "website": "https://www.sngcloud.com",
    "license": "LGPL-3",
    "depends": ["sale_management", "account", "cr_electronic_invoice"],
    "data": [
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
