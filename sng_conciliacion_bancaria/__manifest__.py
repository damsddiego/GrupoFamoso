# -*- coding: utf-8 -*-
{
    'name': 'SNG Conciliación Bancaria con IA',
    'version': '18.0.1.1.0',
    'category': 'Accounting',
    'summary': 'Importa el estado de cuenta del banco (BAC) y deja cada línea '
               'montada con su pago/factura sugerido para conciliar en el '
               'módulo nativo de Odoo',
    'author': 'SNG',
    'license': 'LGPL-3',
    'depends': ['account_accountant'],
    'data': [
        'security/sng_conciliacion_security.xml',
        'security/ir.model.access.csv',
        'data/sng_conciliacion_data.xml',
        'views/sng_conciliacion_views.xml',
    ],
    'installable': True,
    'application': True,
}
