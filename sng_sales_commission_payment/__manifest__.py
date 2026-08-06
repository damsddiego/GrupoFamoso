# -*- coding: utf-8 -*-
{
    'name': 'Comisiones por Pagos de Facturas',
    'version': '18.0.3.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Comisión mensual por vendedor con escala por tramos sobre pagos recibidos',
    'description': """
        Comisiones por Pagos de Facturas
        ==================================

        Este módulo calcula la comisión de cada vendedor a partir del total de pagos
        recibidos durante el mes sobre facturas de cliente, aplicando un cuadro de
        comisiones por tramos (escala).

        Características:
        - Cuadro de comisiones global por tramos (monto mínimo mensual → %).
        - Acumulado mensual por vendedor sobre el monto sin impuestos pagado
          (proporcional a cada pago, incluso parciales).
        - La tasa del tramo alcanzado se aplica a todo el acumulado del mes.
        - Una comisión consolidada por vendedor y mes, con el detalle de pagos.
        - Generación de facturas de compra al vendedor y seguimiento de estado
          (pendiente / facturado / pagado).
    """,
    'author': 'SNG',
    'website': '',
    'depends': [
        'account',
        'report_xlsx',
        'sales_commission_omax',
        'sng_invoice_assigned_salesperson',
        'sng_payment_report_by_salesperson',
    ],
    'data': [
        'security/group_security.xml',
        'security/ir.model.access.csv',
        'data/product_data.xml',
        'data/commission_tier_data.xml',
        'views/sng_commission_tier_views.xml',
        'views/sng_commission_monthly_views.xml',
        'views/sng_commission_payment_line_views.xml',
        'views/account_payment_views.xml',
        'report/sng_commission_monthly_report.xml',
        'wizard/sng_create_commission_bill_wiz.xml',
        'wizard/sng_generate_commission_wiz.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
