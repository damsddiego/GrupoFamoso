# -*- coding: utf-8 -*-

{
    "name": "Reporte de Facturación por Cliente",
    "version": "18.0.1.0.3",
    "category": "Accounting/Reporting",
    "summary": "Facturación neta por cliente con vista en pantalla, PDF y Excel",
    "description": """
Reporte de Facturación por Cliente
==================================

Permite consultar facturas de cliente y notas de crédito publicadas por una
cantidad configurable de meses, uno o todos los clientes, una o varias
compañías y un monto neto mínimo. Los importes se consolidan en la moneda de
cada compañía y se pueden visualizar en pantalla o exportar a PDF y Excel.
    """,
    "author": "SNG",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "views/billing_report_wizard_views.xml",
        "report/billing_report_actions.xml",
        "report/billing_report_templates.xml",
    ],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "installable": True,
    "application": False,
    "auto_install": False,
}
