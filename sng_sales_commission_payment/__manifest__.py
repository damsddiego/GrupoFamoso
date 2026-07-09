# -*- coding: utf-8 -*-
{
    'name': 'Comisiones por Pagos de Facturas',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Cálculo de comisiones por pagos parciales o totales de facturas de cliente',
    'description': """
        Comisiones por Pagos de Facturas
        ==================================

        Este módulo calcula comisiones de vendedor a partir de los pagos recibidos
        sobre facturas de cliente, permitiendo generar comisión incluso cuando el
        pago es parcial.

        Características:
        - Configuración de porcentaje de comisión por vendedor (contacto).
        - Cálculo automático al confirmar/reconciliar un pago.
        - Base de cálculo: monto sin impuestos pagado (proporcional al pago).
        - Generación de facturas de compra al vendedor para el pago de comisiones.
        - Reporte y seguimiento de líneas de comisión por estado.
    """,
    'author': 'SNG',
    'website': '',
    'depends': [
        'account',
        'sales_commission_omax',
        'sng_invoice_assigned_salesperson',
        'sng_payment_report_by_salesperson',
    ],
    'data': [
        'security/group_security.xml',
        'security/ir.model.access.csv',
        'data/product_data.xml',
        'views/sng_commission_config_views.xml',
        'views/sng_commission_payment_line_views.xml',
        'views/account_payment_views.xml',
        'wizard/sng_create_commission_bill_wiz.xml',
        'wizard/sng_generate_commission_wiz.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
