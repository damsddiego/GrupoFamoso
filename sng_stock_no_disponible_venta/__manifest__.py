# -*- coding: utf-8 -*-
{
    'name': 'SNG Ubicaciones no disponibles para venta',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Marca ubicaciones cuyo stock no cuenta como disponible en las '
               'apps de SNG (dañado, desecho, exhibición, marketing).',
    'description': """
Agrega a las ubicaciones la casilla "No disponible para venta".

Cuando una app de SNG consulta existencias con la clave de contexto
``sng_excluir_no_disponible``, las ubicaciones marcadas (y todas las que
cuelgan de ellas) dejan de sumar en qty_available, free_qty y en las
entradas/salidas previstas.

Es opcional por contexto a propósito: la interfaz web de Odoo, las
reservas, el reabastecimiento y la valoración no cambian.
""",
    'author': 'SNG',
    'website': 'https://sngcloud.cr',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'views/stock_location_views.xml',
    ],
    'installable': True,
    'application': False,
}
