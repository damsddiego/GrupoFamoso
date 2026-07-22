# -*- coding: utf-8 -*-
{
    'name': 'SNG Ruteros - Recibos de pago',
    'summary': 'Guarda los recibos creados desde la app app_ruteros sobre account.payment '
               'y agrega un menú para ver los pagos (borradores) de ruteros.',
    'version': '1.4.0',
    'category': 'Accounting',
    'author': 'SNG',
    'website': 'https://sngcloud.com',
    'depends': ['account', 'customer_sequence', 'sales_commission_omax'],
    'data': [
        'data/sng_ia_data.xml',
        'views/account_payment_views.xml',
    ],
    'external_dependencies': {
        'python': ['anthropic'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
