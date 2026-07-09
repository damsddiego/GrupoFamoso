{
    "name": "SNG Custom Name Sale Order",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "summary": "Add Commercial Name column to Sale Order list view",
    "description": """
    This module adds the Commercial Name field from res.partner to the
    Sale Order list view (quotations and orders).
    """,
    "author": "SNG",
    "depends": [
        "sale",
        "sng_custom_name_partner",
    ],
    "data": [
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
