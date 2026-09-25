# -*- coding: utf-8 -*-
{
    "name": "SNG Control de Visitas y Rutas",
    "version": "18.0.1.2.0",
    "category": "Sales",
    "summary": "Control de visitas de agentes de ruta, seguimiento de televentas "
               "y matriz gerencial de cobertura por cliente",
    "description": """
Replica en Odoo la "Matriz Control de visitas y rutas":

* Bloque comercial en la visita del rutero (resultado, monto, motivo sin
  venta, próxima acción, comentario) sobre sng_ruteros_visitas.
* Seguimiento de televentas por cliente y semana, con actividades para la
  responsable de televentas.
* Catálogos editables (motivos, próximas acciones, comentarios).
* Frecuencia de visita por ruta y por cliente.
* Matriz mensual por cliente con estado de atención, efectividad, cliente
  desatendido, responsable del próximo paso y alerta gerencial, más KPIs.
* Crons: generación semanal de pendientes de televentas, recálculo diario
  de la matriz y resumen gerencial semanal en Discuss.
""",
    "author": "SNG",
    "website": "https://sngcloud.cr",
    "license": "LGPL-3",
    "depends": [
        "sale",
        "mail",
        "sng_ruteros_pagos",
        "sng_ruteros_visitas",
        "sng_sales_routes",
        "sales_commission_omax",
        "sng_cxc_report",
    ],
    "data": [
        "security/sng_control_visitas_security.xml",
        "security/ir.model.access.csv",
        "data/sng_visita_catalogo_data.xml",
        "data/mail_data.xml",
        "views/sng_visita_catalogo_views.xml",
        "views/sng_ruteros_visita_views.xml",
        "views/sng_televentas_seguimiento_views.xml",
        "wizard/sng_control_visitas_generar_wizard_views.xml",
        "views/sng_control_visitas_linea_views.xml",
        "views/res_partner_views.xml",
        "views/sng_sales_route_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
        "data/ir_cron_data.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
