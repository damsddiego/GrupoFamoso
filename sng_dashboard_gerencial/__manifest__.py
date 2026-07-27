# -*- coding: utf-8 -*-
{
    'name': 'SNG Dashboard Gerencial',
    'summary': 'Dashboard para toma de decisiones: ventas, cobros, cartera, '
               'inventario y análisis IA con recomendaciones',
    'version': '1.0.0',
    'category': 'Accounting',
    'author': 'SNG',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'stock_account',
        'sales_commission_omax',
        'web',
    ],
    'external_dependencies': {'python': ['anthropic']},
    'data': [
        'security/sng_dashboard_security.xml',
        'security/ir.model.access.csv',
        'data/sng_dashboard_data.xml',
        'views/sng_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sng_dashboard_gerencial/static/src/dashboard/dashboard.js',
            'sng_dashboard_gerencial/static/src/dashboard/dashboard.xml',
            'sng_dashboard_gerencial/static/src/dashboard/dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
}
