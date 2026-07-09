{
    "name": "SNG Custom Name Partner",
    "version": "18.0.1.0.0",
    "category": "Customer Relationship Management",
    "summary": "Add Commercial Name field to Partner model",
    "description": """
    This module adds a Commercial Name field to the Partner model (res.partner).
    """,
    "author": "SNG",
    "depends": [
        "base",
    ],
    "data": [
        "views/res_partner_view.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}