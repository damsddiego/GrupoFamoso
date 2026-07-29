# -*- coding: utf-8 -*-
{
    'name': 'Aprobación de Ajustes de Inventario',
    'version': '18.0.1.0.1',
    'category': 'Inventory/Inventory',
    'summary': 'Flujo de aprobación para ajustes de inventario',
    'description': """
        Permite que usuarios de inventario soliciten ajustes de stock
        y que administradores de inventario los aprueben o rechacen
        antes de que se apliquen al sistema.
    """,
    'author': 'SNG',
    'depends': ['stock', 'product'],
    'data': [
        'security/stock_adjustment_security.xml',
        'wizard/stock_adjustment_reject_wizard_view.xml',
        'security/ir.model.access.csv',
        'data/stock_adjustment_sequence.xml',
        'views/stock_adjustment_request_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
}
