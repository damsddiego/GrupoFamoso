# -*- coding: utf-8 -*-
{
    'name': 'Purchase Import Lines SNG',
    'version': '18.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Import purchase order lines from Excel file',
    'description': """
        Import Purchase Order Lines
        ============================
        This module allows you to import purchase order lines from an Excel file.

        Features:
        ---------
        * Import lines from Excel (.xlsx) file
        * Search products by internal reference (default_code)
        * Update product sale price (list_price)
        * Validate that all products exist before importing
    """,
    'author': 'SNG',
    'website': '',
    'depends': ['purchase', 'product'],
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'data': [
        'security/ir.model.access.csv',
        'wizard/import_wizard_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
