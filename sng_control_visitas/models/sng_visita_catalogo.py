# -*- coding: utf-8 -*-
from odoo import api, fields, models

TIPOS_CATALOGO = [
    ('motivo_sin_venta', 'Motivo sin venta'),
    ('proxima_accion', 'Próxima acción'),
    ('comentario_agente', 'Comentario predeterminado del agente'),
    ('comentario_televentas', 'Comentario predeterminado de televentas'),
]

# Códigos con lógica asociada en el módulo. Se documentan aquí para que no
# se pierdan si gerencia renombra el texto del catálogo.
CODIGO_TRANSFERIR_TELEVENTAS = 'transferir_natalia'
CODIGO_CERRAR_SEGUIMIENTO = 'cerrar_seguimiento'


class SngVisitaCatalogo(models.Model):
    """Listas editables que la matriz gerencial define como desplegables:
    motivos sin venta, próximas acciones y comentarios predeterminados.

    Se usa un solo modelo con `tipo` para que gerencia mantenga todo desde
    una sola pantalla. `codigo` es el gancho estable para la lógica.
    """

    _name = 'sng.visita.catalogo'
    _description = 'Catálogo de control de visitas'
    _order = 'tipo, sequence, id'

    name = fields.Char(string='Texto', required=True, translate=False)
    tipo = fields.Selection(
        TIPOS_CATALOGO, string='Tipo', required=True, index=True)
    codigo = fields.Char(
        string='Código',
        index=True,
        help='Identificador estable usado por la lógica del módulo '
             '(por ejemplo "transferir_natalia"). No cambiarlo.',
    )
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
    descripcion = fields.Text(string='Descripción')

    _sql_constraints = [
        ('codigo_tipo_uniq', 'unique(tipo, codigo)',
         'Ya existe un registro del catálogo con ese código y tipo.'),
    ]

    @api.model
    def _sng_buscar_codigo(self, tipo, codigo):
        """Devuelve el registro (activo o no) de un tipo/código dado."""
        if not codigo:
            return self.browse()
        return self.with_context(active_test=False).search(
            [('tipo', '=', tipo), ('codigo', '=', codigo)], limit=1)
