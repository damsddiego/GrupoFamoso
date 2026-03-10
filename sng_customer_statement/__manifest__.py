# -*- coding: utf-8 -*-
{
    'name': 'Estado de Cuenta de Clientes',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Reporte de estado de cuenta por cliente: facturas, pagos aplicados, saldos y aging.',
    'description': """
        Genera un reporte "Estado de Cuenta de Clientes" con:
        - Modo resumen: KPIs por cliente (facturado, pagado, residual, aging)
        - Modo detalle: ledger cronológico por cliente
        - Exclusión de facturas rechazadas por tributación (state_tributacion = 'Rechazado')
        - Pagos en borrador visibles como "Pendiente por aplicar" (sin afectar saldo contable)
        - Exportación PDF (QWeb) y XLSX
        - Filtros: fecha, cliente, empresa, vendedor, etiquetas, moneda, etc.
    """,
    'author': 'SNG Cloud',
    'website': 'https://www.sngcloud.com',
    'depends': [
        'account',
        'base_setup',
        'customer_sequence',
    ],
    'data': [
        # 1. Grupos primero — el CSV los necesita
        'security/security_rules.xml',
        # 2. ACL — ahora los grupos existen
        'security/ir.model.access.csv',
        # 3. Vistas y acciones
        'wizard/customer_statement_wizard_view.xml',
        'views/customer_statement_views.xml',
        'report/customer_statement_report.xml',
        'report/customer_statement_template.xml',
        'views/menu_views.xml',
        # 4. ACL modelos persistentes — en XML porque los external IDs
        #    model_customer_statement_report / model_customer_statement_report_line
        #    no existen aún cuando se procesa el CSV (paso 2).
        #    En XML con ref=, Odoo los resuelve cuando este archivo se carga,
        #    momento en que los modelos ya están registrados en ir.model.
        'security/model_access.xml',
        # 5. Record rules AL FINAL — requieren que model_customer_statement_report
        #    y model_customer_statement_report_line ya estén en ir.model.
        #    Odoo registra los modelos Python en ir.model al inicio del upgrade,
        #    pero sus external IDs se consolidan después de cargar el ACL.
        #    Poner las rules aquí evita "External ID not found: model_customer_statement_report".
        'security/record_rules.xml',
    ],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
}
