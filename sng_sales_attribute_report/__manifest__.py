# -*- coding: utf-8 -*-

{
    "name": "Facturación por atributos",
    "version": "18.0.1.0.0",
    "category": "Accounting/Reporting",
    "summary": "Facturación neta por atributos, vendedor y estado de Hacienda",
    "description": """
Facturación por atributos
==========================

Reporte multicompañía de facturas y notas de crédito aceptadas por Hacienda.
Los importes se calculan únicamente con las líneas cuyos productos cumplen la
combinación seleccionada de atributos y valores. Incluye consulta en pantalla,
PDF, Excel y auditoría de documentos excluidos.
    """,
    "author": "SNG Cloud",
    "website": "https://sngcloud.app/",
    "license": "LGPL-3",
    "depends": [
        "account",
        "product",
        "cr_electronic_invoice",
        "sales_commission_omax",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sales_attribute_report_views.xml",
        "report/sales_attribute_report_actions.xml",
        "report/sales_attribute_report_templates.xml",
    ],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "installable": True,
    "application": False,
    "auto_install": False,
}
