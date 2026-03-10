# -*- coding: utf-8 -*-
{
    'name': 'Sales Analysis Custom',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': 'Custom Sales Analysis Reports - Salesperson from Partner',
    'author': 'SNG',
    'website': 'https://sngcloud.com',
    'description': """
Custom Sales Analysis Module
=============================

This module extends the standard Odoo Sales Analysis (sale.report) to:
- Change the salesperson source to come from the customer's assigned salesperson
- The salesperson is determined by the partner contact with is_salesperson = True
    """,
    'depends': [
        'sale',
        'sales_commission_omax',  # Required for salesperson_id field
    ],
    'data': [
        'views/sale_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
