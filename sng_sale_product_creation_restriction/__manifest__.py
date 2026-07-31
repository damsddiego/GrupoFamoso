# -*- coding: utf-8 -*-
{
    "name": "SNG Restricción de Creación de Productos en Ventas",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "summary": "Evita crear productos accidentalmente desde cotizaciones",
    "author": "SNG",
    "license": "LGPL-3",
    "depends": ["sale"],
    "data": [
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
