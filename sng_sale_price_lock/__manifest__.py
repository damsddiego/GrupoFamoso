# -*- coding: utf-8 -*-
{
    'name': 'SNG Bloqueo de Precio y Descuento en Ventas',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Impide modificar el precio unitario o el descuento de una linea '
               'de venta cuando el valor no proviene de la lista de precios',
    'description': """
        Bloqueo duro (validado en servidor) del precio unitario y del descuento
        en las lineas de pedido de venta.

        El precio y el descuento se recalculan desde la lista de precios del
        pedido y se comparan contra lo que el usuario intenta guardar. Si no
        coinciden se lanza un error, salvo que el usuario pertenezca al grupo
        de excepcion.

        Se valida en create() y write(), por lo que tambien aplica a
        importaciones, XML-RPC y al asistente nativo de descuentos.
    """,
    'author': 'SNG',
    'website': 'https://www.sngcloud.com',
    'depends': ['sale'],
    'data': [
        'security/sng_sale_price_lock_security.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
