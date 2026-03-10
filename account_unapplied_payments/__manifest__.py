{
    'name': 'Pagos no aplicados',
    'version': '18.0.1.0.1',
    'summary': 'Lista pagos publicados sin conciliar y permite asignarlos a facturas en un solo paso.',
    'author': 'SNG CLOUD',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_invoice_match_wizard_views.xml',
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'application': False,
}
