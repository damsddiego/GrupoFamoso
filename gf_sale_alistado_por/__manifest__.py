{
    'name': 'GF - Alistado por (Sale Order)',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Agrega el campo "Alistado por" (responsable de alistado) en pedidos de venta',
    'description': """
        Este módulo agrega el campo x_gf_alistado_por (Many2one a res.users) en el
        modelo sale.order para registrar el usuario que realizó el alistado del pedido.
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
