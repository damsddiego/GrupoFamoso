{
    'name': 'SNG - Reimpresión de tickets de bodega',
    'version': '18.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Autorizar desde Odoo la reimpresión de un ticket de alistado, con permiso y bitácora',
    'description': """
Reimpresión de tickets de bodega
================================

El agente de impresión imprime cada orden **una sola vez**. La única forma de
sacar un segundo ticket es crear una autorización de un solo uso en Firebase
(`/print_reprint_approvals/{orderId}`), lo que hasta ahora obligaba a entrar a
la consola de Firebase a mano.

Este módulo pone esa autorización dentro de Odoo:

* Un botón "Reimprimir ticket" en la orden de venta, visible solo para el grupo
  *Autorizar reimpresión de tickets*.
* Un asistente que obliga a escribir el motivo y advierte en rojo si la
  mercadería ya salió de bodega.
* Bitácora propia en Odoo (`sng.reimpresion.log`) con quién, cuándo, por qué y
  qué respondió el servicio. Los intentos fallidos también quedan registrados.

Odoo NO habla con Firebase directamente: llama a un webhook de n8n, que es
quien tiene la credencial de la base. Así Odoo no obtiene ningún poder sobre
`/print_ledger`, que es el registro que impide los tickets duplicados.

Ver `doc/README.md` para la instalación y el workflow de n8n.
    """,
    'author': 'SNG CLOUD',
    'website': 'https://www.sngcloud.com',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'sale_stock',
        'stock',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/sng_reimpresion_log_views.xml',
        'wizard/sng_reimpresion_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
