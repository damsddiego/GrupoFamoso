# -*- coding: utf-8 -*-
{
    'name': 'SNG Ruteros - Notas por línea de venta',
    'summary': 'Agrega el campo sng_line_note a las líneas de pedido de venta, usado por la app móvil app_ruteros.',
    'version': '1.0.0',
    'category': 'Sales',
    'author': 'SNG',
    'website': 'https://sngcloud.com',
    'depends': ['sale'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
