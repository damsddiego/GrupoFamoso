# -*- coding: utf-8 -*-
{
    "name": "SNG Importar Promociones a Listas de Precios",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "summary": "Importa precios de remate desde Excel a todas las listas de precios",
    "author": "SNG",
    "license": "LGPL-3",
    "depends": ["sale"],
    "external_dependencies": {
        "python": ["openpyxl"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/pricelist_promotion_import_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
