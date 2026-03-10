# -*- coding: utf-8 -*-
{
    'name': 'SNG Invoice Report Custom',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Añade código del cliente en el reporte de Análisis de Facturas',
    'description': """
        Este módulo extiende el reporte de Análisis de Facturas para mostrar
        el código del cliente concatenado con su nombre (unique_id - name).
    """,
    'author': 'SNG',
    'depends': ['account', 'customer_sequence'],
    'data': [
        'views/account_invoice_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
