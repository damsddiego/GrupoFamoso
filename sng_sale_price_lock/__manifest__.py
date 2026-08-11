# -*- coding: utf-8 -*-
{
    'name': 'SNG Bloqueo de Precio y Descuento en Ventas',
    'version': '18.0.1.1.1',
    'category': 'Sales',
    'summary': 'Impide modificar precios o descuentos fuera de lista en ventas '
               'y facturas de cliente',
    'description': """
        Bloqueo duro (validado en servidor) del precio unitario y del descuento
        en las lineas de pedido de venta y de factura de cliente.

        El precio y el descuento se recalculan desde la lista de precios y se
        comparan contra lo que el usuario intenta guardar. En facturas creadas
        desde ventas se respetan los valores de la linea de pedido; en facturas
        manuales se utiliza la lista de precios del cliente. Si no coinciden se
        lanza un error, salvo que el usuario pertenezca al grupo de excepcion.

        Se valida en create() y write(), por lo que tambien aplica a
        importaciones, XML-RPC y al asistente nativo de descuentos. Las
        facturas se vuelven a validar antes de contabilizarlas.
    """,
    'author': 'SNG',
    'website': 'https://www.sngcloud.com',
    'depends': ['sale'],
    'data': [
        'security/sng_sale_price_lock_security.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
