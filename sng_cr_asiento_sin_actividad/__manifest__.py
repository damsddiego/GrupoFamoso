{
    "name": "SNG Asientos sin Actividad Economica",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "No exige actividad economica en asientos contables (move_type entry)",
    "author": "SNG",
    "website": "https://www.sngcloud.com",
    "license": "LGPL-3",
    "depends": ["account", "cr_electronic_invoice", "cr_import_vendor_bills"],
    "data": [
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
