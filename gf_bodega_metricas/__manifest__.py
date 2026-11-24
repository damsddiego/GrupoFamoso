{
    'name': 'GF - Métricas de bodega',
    'version': '18.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Registro de alistados y actividades de los empleados de bodega desde la app GF',
    'description': """
        Guarda un registro por cada bloque de trabajo que un empleado de bodega hace
        desde las tabletas (app Android GF): alistado de órdenes y otras actividades
        como acomodar bodega. Cada registro guarda empleado, tableta, inicio, fin,
        duración y, en el alistado, líneas y unidades.

        Los empleados se identifican con PIN en la app (Firebase); aquí se guardan
        como texto. La app escribe con el usuario técnico, que necesita el grupo
        Inventario / Usuario.
    """,
    'author': 'SNG CLOUD',
    'website': 'https://www.sngcloud.com',
    'license': 'LGPL-3',
    'depends': ['sale_stock', 'gf_sale_alistado_por'],
    'data': [
        'security/ir.model.access.csv',
        'data/gf_bodega_actividad_data.xml',
        'views/gf_bodega_actividad_views.xml',
        'views/gf_bodega_registro_views.xml',
        'views/sale_order_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
