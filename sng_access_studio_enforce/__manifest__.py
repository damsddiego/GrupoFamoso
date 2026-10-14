# -*- coding: utf-8 -*-
{
    "name": "SNG Access Studio: bloqueo en servidor",
    "summary": (
        "Permite que una regla de botón de User Access Studio también "
        "bloquee el método en el servidor (RPC/API), no solo en la vista."
    ),
    "version": "18.0.1.0.0",
    "author": "SNG",
    "license": "LGPL-3",
    "category": "Productivity/Tools",
    "depends": [
        "eh_access_studio",
        "sale",
    ],
    "data": [
        "views/eh_access_profile_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
