# -*- coding: utf-8 -*-
{
    'name': 'SNG Credit Note Report',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Reporte de Notas de Crédito con exportación a Excel',
    'description': """
        Reporte de Notas de Crédito
        ============================

        Este módulo proporciona un reporte completo de Notas de Crédito de clientes que incluye:

        * Vista de lista con filtros avanzados
        * Información del cliente (unique_id, nombre)
        * Datos de la nota de crédito (número, fecha, monto, motivo)
        * Facturas relacionadas mediante reconciliación contable
        * Exportación a Excel (XLSX)
        * Optimizado con SQL VIEW para alto rendimiento
        * Soporte multi-compañía

        El reporte utiliza las reconciliaciones contables (account.partial.reconcile) para determinar
        las facturas originales relacionadas a cada nota de crédito, proporcionando trazabilidad completa.
    """,
    'author': 'SNG',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sng_credit_note_report_views.xml',
        'wizard/sng_credit_note_export_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
