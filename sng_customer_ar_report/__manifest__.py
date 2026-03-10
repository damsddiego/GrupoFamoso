# -*- coding: utf-8 -*-
{
    'name': 'Reporte CxC por Cliente (Facturado, Pendiente, Días promedio de pago)',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Reporte de Cuentas por Cobrar por cliente con total facturado, pendiente y días promedio de pago',
    'description': """
Reporte CxC por Cliente
========================
Muestra por cliente:
- Total Facturado (facturas posteadas)
- Total Pendiente (saldo residual)
- Días promedio de pago (días entre factura y último pago)

Características:
- SQL VIEW para máxima eficiencia
- Vistas List y Pivot
- Filtros por fecha, compañía, cliente, saldo
- Multi-compañía compatible
- Exportable a Excel con botón estándar
    """,
    'author': 'SNG',
    'depends': ['account', 'customer_sequence'],
    'data': [
        'security/ir.model.access.csv',
        'views/sng_customer_ar_report_views.xml',
        'views/sng_customer_ar_report_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
