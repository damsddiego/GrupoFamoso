# -*- coding: utf-8 -*-
{
    'name': 'SNG MQTT Bus - Eventos en tiempo real para ruteros',
    'summary': 'Publica eventos de Odoo (clientes creados/modificados/'
               'archivados) a un broker MQTT para que la app app_ruteros '
               'sincronice casi en tiempo real.',
    'version': '1.0.0',
    'category': 'Technical',
    'author': 'SNG',
    'website': 'https://sngcloud.com',
    'depends': ['base', 'sales_commission_omax'],
    'data': [],
    'external_dependencies': {
        'python': ['paho.mqtt.publish'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
