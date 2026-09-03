"""Bitacora de reimpresiones del lado de Odoo.

Es independiente de /print_audit en Firebase a proposito: si alguien manipula la
base en tiempo real, este registro sigue diciendo quien pidio que. Guarda el
nombre de la orden como texto ademas del enlace, para que la fila siga siendo
legible aunque la orden se renombre o se borre.
"""
from odoo import fields, models


class SngReimpresionLog(models.Model):
    _name = 'sng.reimpresion.log'
    _description = 'Bitacora de reimpresiones de ticket'
    _order = 'create_date desc, id desc'

    order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Orden',
        ondelete='set null',
        index=True,
    )
    order_ref = fields.Char(
        string='Referencia',
        required=True,
        help='Nombre de la orden al momento del intento. Se guarda como texto '
             'para que la bitacora sobreviva a un renombrado o borrado.',
    )
    odoo_order_id = fields.Integer(
        string='ID de orden',
        required=True,
        help='Id de la sale.order. Es la clave con la que el agente identifica '
             'la orden; no confundir con el numero del documento.',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Autorizado por',
        required=True,
        index=True,
    )
    motivo = fields.Text(string='Motivo', required=True)
    resultado = fields.Selection(
        selection=[('ok', 'Autorizada'), ('error', 'Fallo')],
        string='Resultado',
        required=True,
        index=True,
    )
    detalle = fields.Text(
        string='Detalle',
        help='Respuesta del servicio de impresion, o el error si fallo.',
    )
    copias_previas = fields.Integer(
        string='Copias previas',
        help='Cuantas veces se habia impreso la orden antes de este intento, '
             'segun el ledger. 0 si no se pudo consultar.',
    )
    entrega_despachada = fields.Boolean(
        string='Ya despachada',
        help='La orden tenia al menos una entrega en estado hecho cuando se '
             'autorizo la reimpresion.',
    )

    def _compute_display_name(self):
        for registro in self:
            registro.display_name = '%s - %s' % (
                registro.order_ref or '?',
                registro.user_id.name or '?',
            )
