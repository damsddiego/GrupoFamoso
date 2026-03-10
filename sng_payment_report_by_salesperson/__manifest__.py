# -*- coding: utf-8 -*-
{
    'name': 'Payment Report',
    'version': '18.0.2.1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Reporte de pagos con información de facturas',
    'description': """
        Reporte de Pagos
        ================

        Este módulo provee un reporte completo de pagos que muestra:
        - Nombre del cliente
        - Monto del pago
        - Factura aplicada (si está reconciliado)
        - Días transcurridos desde emisión hasta pago
        - Monto de la factura sin impuestos
        - Estado de reconciliación
        - Filtros por rango de fechas y estado
    """,
    'author': 'SNG',
    'website': '',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_report_salesperson_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}