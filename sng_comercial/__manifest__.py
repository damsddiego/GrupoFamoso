# -*- coding: utf-8 -*-
{
    'name': 'Comercial',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'App de reportes comerciales: Sell in / Sell out por pilar, base y volumen',
    'description': """
Comercial
=========
App propia para los reportes comerciales de SNG. No cuelga de Ventas, Compras
ni de otro módulo: cada reporte nuevo se agrega aquí.

Primer reporte: Sell in / Sell out
----------------------------------
* Sell in: compras recibidas (órdenes de compra, menos devoluciones a proveedor).
* Sell out: cantidades facturadas de órdenes de venta (menos notas de crédito).
* Unidades y litros, por mes, pilar, base, volumen y producto.
* Inventario comercial: stock, tránsito y bodega del grupo.
* Excel con marca desde un asistente.

Entran los productos que tienen el atributo marcado como PILAR.
    """,
    'license': 'LGPL-3',
    'author': 'SNG',
    'depends': [
        'account',
        'purchase_stock',
        'sale_stock',
    ],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [
        'security/sng_comercial_security.xml',
        'security/ir.model.access.csv',
        'views/sng_comercial_sell_report_views.xml',
        'views/sng_comercial_inventario_report_views.xml',
        'wizard/sng_comercial_sell_wizard_views.xml',
        'views/configuracion_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
