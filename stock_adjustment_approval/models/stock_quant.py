# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, _, api, models
from odoo.exceptions import AccessError

GRUPO_AJUSTE_DIRECTO = 'stock_adjustment_approval.group_stock_ajuste_directo'
CLAVE_SOLICITUD_APROBADA = 'stock_adjustment_request_apply'
# Marca que solo este módulo puede poner en el contexto: un objeto de Python
# no viaja por RPC, así que nadie lo falsifica desde la API.
SOLICITUD_APROBADA = object()


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def _ajuste_directo_permitido(self):
        # env.user es el usuario real aunque el código corra con sudo(), como
        # pasa al crear existencias nuevas desde la lista editable.
        return (
            self.env.context.get(CLAVE_SOLICITUD_APROBADA) is SOLICITUD_APROBADA
            or self.env.uid == SUPERUSER_ID
            or self.env.user.has_group(GRUPO_AJUSTE_DIRECTO)
        )

    def _apply_inventory(self):
        # Todos los caminos que cambian una cantidad sin traslado terminan
        # aquí: «Actualizar cantidad», conteo físico, importación, borrar un
        # quant y el asistente de cantidad del producto.
        if not self._ajuste_directo_permitido():
            raise AccessError(_(
                "No puede cambiar cantidades de inventario directamente. Haga una "
                "solicitud de ajuste para que la apruebe otra persona."
            ))
        return super()._apply_inventory()

    @api.model
    def _get_quants_action(self, domain=None, extend=False):
        # Sin el grupo, la lista de existencias se abre de solo lectura.
        if not self._ajuste_directo_permitido():
            self = self.with_context(inventory_mode=False)
        return super()._get_quants_action(domain=domain, extend=extend)
