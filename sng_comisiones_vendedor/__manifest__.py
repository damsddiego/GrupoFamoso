# -*- coding: utf-8 -*-
{
    'name': 'Estado de comisiones del vendedor',
    'version': '18.0.1.1.0',
    'category': 'Sales/Commission',
    'summary': 'Cruces de pagos y comisiones por vendedor para la app (Mis comisiones) y la oficina',
    'description': """
        Estado de comisiones del vendedor
        =================================

        Un solo método (``sng.comision.estado.obtener_estado``) que la app de
        ruteros llama por RPC para mostrar «Mis comisiones», y un asistente con
        la misma información para la oficina:

        - Resumen por compañía: base, tramo, comisión (estimada si el mes está
          abierto), ajustes, cobros en proceso y cuánto falta para el
          siguiente tramo.
        - Pagos reportados por el vendedor contra verificados, no aplicados,
          anulados y rechazados.
        - Anulados que se rehicieron, pagos automáticos de feria anulados y
          anulados sin reemplazo.
        - Comisión del vendedor registrada por otro vendedor o por oficina, y
          pagos que él registró cuya comisión es de otro.
        - Pagos sin comisión con su motivo, y reversos del mes.

        Seguridad: solo el grupo «Comisiones: consulta desde la app de ruteros»
        (asignarlo al usuario RPC de la app) y los usuarios de comisiones
        pueden llamar el método.

        Incluye un cron (apagado al instalar) que genera las líneas de
        comisión que faltan de los cobros de la app.
    """,
    'author': 'SNG',
    'depends': [
        'mail',
        'sng_sales_commission_payment',
        'sng_ruteros_pagos',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'wizard/sng_comision_estado_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
