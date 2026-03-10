{
    'name': 'Sale Order Shipping Method',
    'version': '18.0.1.0.1',
    'category': 'Sales',
    'summary': 'Agrega campo de método de envío en pedidos de venta y facturas',
    'description': """
        Este módulo agrega un campo de texto opcional llamado "Método de envío"
        en el header del formulario de pedidos de venta (sale.order) y facturas (account.move).
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'license': 'LGPL-3',
    'depends': ['sale', 'account'],
    'data': [
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
