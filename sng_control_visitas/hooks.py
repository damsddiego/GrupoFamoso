# -*- coding: utf-8 -*-
import logging

from odoo import fields

_logger = logging.getLogger(__name__)

# Usuarios de Grupo Famoso. Si un login no existe (base de pruebas, otro
# cliente) simplemente se omite; después se ajusta en Ventas › Ajustes ›
# Control de visitas y en los grupos del usuario.
LOGIN_TELEVENTAS = 'callcenter@grupofsa.net'
LOGINS_GERENCIA = ('gerencia@grupofsa.net',)

# Clientes genéricos de tiquete: uno por agente/canal (OCASIONAL ALLAN
# MAYORISTA TIQUETE...) más el cliente ocasional público.
PATRONES_GENERICOS = ('ocasional %', 'cliente ocasional%', 'cliente ocacional%')


def marcar_clientes_genericos(env):
    """Marca los clientes genéricos para que no entren en la matriz."""
    Partner = env['res.partner'].with_context(active_test=False)
    dominio = ['|'] * (len(PATRONES_GENERICOS) - 1) + [
        ('name', '=ilike', patron) for patron in PATRONES_GENERICOS]
    genericos = Partner.search(
        [('sng_excluir_matriz', '=', False)] + dominio)
    genericos.write({'sng_excluir_matriz': True})
    _logger.info(
        'sng_control_visitas: %s clientes genéricos excluidos de la matriz: %s',
        len(genericos), ', '.join(genericos.mapped('name')))
    return genericos


def post_init_hook(env):
    """Configuración inicial.

    Todo es idempotente y tolerante: si un usuario o ruta no existe (por
    ejemplo en una base de pruebas) simplemente se omite.
    """
    Users = env['res.users']
    grupo_user = env.ref('sng_control_visitas.group_control_visitas_user')
    grupo_manager = env.ref('sng_control_visitas.group_control_visitas_manager')

    televentas = Users.search([('login', '=', LOGIN_TELEVENTAS)], limit=1)
    if televentas:
        televentas.write({'groups_id': [(4, grupo_user.id)]})
        for company in env['res.company'].search([]):
            if not company.sng_televentas_user_id:
                company.sng_televentas_user_id = televentas
    else:
        _logger.warning(
            'sng_control_visitas: no existe el usuario de televentas %s; '
            'configurarlo en Ventas › Ajustes › Control de visitas.',
            LOGIN_TELEVENTAS)
    gerencia = Users.search([('login', 'in', list(LOGINS_GERENCIA))])
    if gerencia:
        gerencia.write({'groups_id': [(4, grupo_manager.id)]})
    env.ref('base.user_admin').write({'groups_id': [(4, grupo_manager.id)]})

    # Tipo de atención por nombre de ruta (las rutas TELEVENTAS / OFICINA /
    # CORPORATIVO no se visitan en sitio). En Grupo Famoso las rutas son
    # provincias, así que normalmente no aplica ninguna regla.
    Route = env['sng.sales.route'].with_context(active_test=False)
    for route in Route.search([]):
        nombre = (route.name or '').strip().upper()
        if 'TELEVENTAS' in nombre:
            route.sng_tipo_atencion = 'televentas'
        elif nombre in ('OFICINA', 'CORPORATIVO'):
            route.sng_tipo_atencion = 'oficina'
        elif 'INACTIVO' in nombre or 'INCOBRABLE' in nombre:
            route.sng_frecuencia_visita = 'sin_visita'

    marcar_clientes_genericos(env)

    # Matriz del mes actual para que el menú no aparezca vacío.
    hoy = fields.Date.today()
    Linea = env['sng.control.visitas.linea']
    for company in env['res.company'].search([]):
        try:
            Linea._sng_generar_mes(hoy, company)
        except Exception:  # noqa: BLE001
            _logger.exception(
                'sng_control_visitas: no se pudo generar la matriz inicial '
                'para %s', company.name)
