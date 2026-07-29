{
    "name": "SNG Custom Name Invoice",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "summary": "Add Commercial Name column to Invoice list view",
    "description": """
    This module adds the Commercial Name field from res.partner to the
    Invoice list view (customer invoices and vendor bills).
    """,
    "author": "SNG",
    "depends": [
        "account",
        "sng_custom_name_partner",
    ],
    "data": [
        "views/account_move_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
