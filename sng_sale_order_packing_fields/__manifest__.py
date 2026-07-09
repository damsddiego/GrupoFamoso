{
    'name': 'SNG Sale Order Packing Fields',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Add packing fields to sale orders (Atado, Caja, Paquete)',
    'author': 'SNG',
    'depends': ['sale'],
    'data': [
        'views/sale_order_view.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
}
