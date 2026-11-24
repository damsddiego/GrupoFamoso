# -*- coding: utf-8 -*-
{
    'name': 'SNG Vendedor en Análisis de Facturas y tablero Facturación',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Vendedor (contacto de sales_commission_omax) en el reporte '
               'Análisis de facturas y en el tablero Facturación',
    'description': """
Expone el vendedor real de la factura (account.move.salesperson_id, un
contacto con is_salesperson definido por sales_commission_omax) en:

* el reporte SQL Análisis de facturas (account.invoice.report): columna,
  búsqueda y agrupación «Vendedor (Contacto)»;
* el tablero Tableros > Facturación: el filtro «Vendedor» y la tabla
  «Top vendedores» usan ese contacto en vez del usuario de Odoo.
    """,
    'author': 'SNG',
    'depends': [
        'account',
        'sales_commission_omax',
        'sng_invoice_report_custom',
        'spreadsheet_dashboard_account',
    ],
    'data': [
        'views/account_invoice_report_views.xml',
        'data/spreadsheet_dashboard.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
