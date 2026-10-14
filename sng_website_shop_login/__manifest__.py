{
    'name': 'SNG - Tienda solo para clientes registrados',
    'version': '18.0.1.0.2',
    'summary': 'Oculta el catálogo de la tienda a visitantes sin sesión, por sitio web',
    'description': """
Por sitio web, opción "Tienda solo para clientes registrados":

* /shop y sus páginas (categorías, productos, comparar, favoritos...) redirigen al login.
* Una regla global oculta productos a visitantes sin sesión en ese sitio: tampoco
  aparecen en el buscador, en los snippets del tema ni en el sitemap.
* El login muestra un aviso para pedir acceso al asesor.

Los demás sitios no cambian.
    """,
    'author': 'SNG',
    'category': 'Website/Website',
    'license': 'LGPL-3',
    'depends': ['website_sale'],
    'data': [
        'security/ir_rule.xml',
        'views/res_config_settings_views.xml',
        'views/templates.xml',
    ],
    'installable': True,
}
