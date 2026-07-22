# -*- coding: utf-8 -*-
{
    "name": "SNG Conciliacion Masiva de Pagos Borrador",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "summary": "Compara un extracto bancario (Excel/CSV) contra pagos en borrador y los postea en bloque cuando coinciden.",
    "author": "SNG",
    "license": "LGPL-3",
    "depends": ["account"],
    "external_dependencies": {
        "python": ["openpyxl"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/bank_statement_match_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
