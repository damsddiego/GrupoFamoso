# -*- coding: utf-8 -*-
{
    'name': 'SNG Plan Comercial Clientes',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Planificacion comercial anual por cliente con segmentacion y exportacion XLSX',
    'license': 'AGPL-3',
    'author': 'SNG',
    'depends': [
        'account',
        'contacts',
        'regalarte_customer_metrics',
        'sale_management',
    ],
    'data': [
        'security/sng_plan_comercial_security.xml',
        'security/ir.model.access.csv',
        'views/sng_commercial_plan_views.xml',
        'views/sng_commercial_plan_line_views.xml',
        'views/sng_commercial_plan_export_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
}
