{
    'name': 'Sale Order Header Notes',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Agregar notas visibles en el encabezado de cotizaciones y pedidos',
    'description': """
        Este módulo agrega un campo de notas en el encabezado del formulario de
        cotizaciones y pedidos de venta (sale.order).
    """,
    'author': 'SNG CLOUD',
    'website': 'https://www.sngcloud.com',
    'license': 'LGPL-3',
    'depends': ['sale'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
