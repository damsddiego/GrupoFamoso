# -*- coding: utf-8 -*-
{
    'name': 'SNG Ruteros - Visitas de vendedor',
    'summary': 'Registro de visitas de los ruteros a clientes (GPS, distancia, '
               'resultado) enviadas desde la app app_ruteros. Deja rastro de '
               'las visitas que no terminan en venta ni cobro.',
    'version': '1.1.0',
    'category': 'Sales',
    'author': 'SNG',
    'website': 'https://sngcloud.com',
    'depends': ['sale', 'account', 'sng_ruteros_pagos'],
    'data': [
        'security/ir.model.access.csv',
        'security/sng_ruteros_visita_rules.xml',
        'views/sng_ruteros_visita_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
