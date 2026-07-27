# -*- coding: utf-8 -*-
{
    'name': 'SNG Análisis de Crédito con IA',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Evaluación de apertura de crédito con IA: estudio de buró (PDF) '
               '+ comportamiento del cliente en todas las compañías del grupo',
    'author': 'SNG',
    'license': 'LGPL-3',
    'depends': ['account', 'mail'],
    'data': [
        'security/sng_credito_security.xml',
        'security/ir.model.access.csv',
        'data/sng_credito_data.xml',
        'views/sng_credito_views.xml',
    ],
    'installable': True,
    'application': True,
}
