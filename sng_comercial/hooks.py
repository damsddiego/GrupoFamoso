# -*- coding: utf-8 -*-

ROLES_POR_NOMBRE = (('pilar', 'PILAR'), ('base', 'BASE'), ('volumen', 'VOLUMEN'))


def post_init_hook(env):
    """Marca los atributos PILAR / BASE / VOLUMEN que ya existen.

    Se crearon a mano (sin XML ID), así que se buscan por nombre y solo se
    marcan si no hay ambigüedad. Al marcar el de volumen, el propio modelo
    propone los litros de cada valor.
    """
    Attribute = env['product.attribute']
    for rol, nombre in ROLES_POR_NOMBRE:
        if Attribute.search_count([('sng_comercial_rol', '=', rol)]):
            continue
        candidatos = Attribute.search([('name', '=ilike', nombre)])
        if len(candidatos) == 1:
            candidatos.sng_comercial_rol = rol
