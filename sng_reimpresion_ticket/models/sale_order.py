from odoo import _, models
from odoo.exceptions import UserError

GRUPO = 'sng_reimpresion_ticket.group_reimpresion_ticket'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _sng_entregas_estado(self):
        """(despachada, detalle) segun las entregas de la orden.

        despachada = salio mercaderia al menos una vez. Es la senal de peligro:
        un ticket de alistado para una orden ya despachada puede terminar en un
        doble surtido, que es justo lo que el control de impresion unica existe
        para evitar.
        """
        self.ensure_one()
        etiquetas = dict(
            self.env['stock.picking'].fields_get(['state'])['state']['selection']
        )
        pickings = self.picking_ids.sorted('id')
        despachada = any(p.state == 'done' for p in pickings)
        detalle = ', '.join(
            '%s: %s' % (p.name, etiquetas.get(p.state, p.state)) for p in pickings
        )
        return despachada, detalle

    def action_sng_reimprimir_ticket(self):
        self.ensure_one()
        if not self.env.user.has_group(GRUPO):
            raise UserError(_(
                'No tiene permiso para autorizar reimpresiones de ticket.'))
        if self.state not in ('sale', 'done'):
            etiquetas = dict(self.fields_get(['state'])['state']['selection'])
            raise UserError(_(
                'Solo se puede reimprimir el ticket de una orden confirmada. '
                'Esta orden esta en estado "%s".'
            ) % etiquetas.get(self.state, self.state))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Autorizar reimpresion de ticket'),
            'res_model': 'sng.reimpresion.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }
