from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    """Bloqueo de órdenes por tableta para la app GF.

    Todas las tabletas entran a Odoo con el mismo usuario técnico, así que
    x_gf_alistado_por (res.users) no distingue quién tiene la orden. Estos campos
    guardan qué tableta y qué empleado la tienen tomada. La app llama a
    gf_tomar_alistado / gf_liberar_alistado por JSON-RPC; no renombrarlos sin
    actualizar la app (data/odoo/OdooApi.kt).

    Para liberar a mano una orden de una tableta que se dañó, basta con vaciar
    "Alistado por" en la orden.
    """

    _inherit = 'sale.order'

    x_gf_alistado_dispositivo = fields.Char(
        string='Tableta de alistado',
        index=True,
        copy=False,
        help='Tableta que tiene tomada la orden para alistarla.',
    )
    x_gf_alistado_empleado = fields.Char(
        string='Empleado de alistado',
        copy=False,
        help='Empleado (PIN de la app) que tiene tomada la orden.',
    )
    x_gf_alistado_desde = fields.Datetime(string='Alistando desde', copy=False)

    def _gf_tomada_por_otra_tableta(self, dispositivo):
        self.ensure_one()
        return bool(
            self.x_gf_alistado_por
            and self.x_gf_alistado_dispositivo
            and self.x_gf_alistado_dispositivo != dispositivo
        )

    def gf_tomar_alistado(self, dispositivo, empleado_nombre):
        """Toma la orden para esta tableta, o falla si otra la tiene.

        Si dos tabletas la toman al mismo tiempo, las dos escriben la misma fila:
        PostgreSQL rechaza la segunda escritura por acceso concurrente, Odoo
        reintenta la llamada y en el reintento ya ve la orden tomada.
        """
        self.ensure_one()
        if self._gf_tomada_por_otra_tableta(dispositivo):
            raise UserError(_(
                'Esta orden ya está siendo alistada por %(empleado)s en la tableta %(tableta)s.',
                empleado=self.x_gf_alistado_empleado or _('otro empleado'),
                tableta=self.x_gf_alistado_dispositivo,
            ))
        self.write({
            'x_gf_alistado_por': self.env.uid,
            'x_gf_alistado_dispositivo': dispositivo,
            'x_gf_alistado_empleado': empleado_nombre,
            'x_gf_alistado_desde': fields.Datetime.now(),
        })
        return True

    def gf_liberar_alistado(self, dispositivo):
        """Libera solo las órdenes que tiene esta tableta (o que no tienen tableta)."""
        propias = self.filtered(
            lambda o: not o.x_gf_alistado_dispositivo or o.x_gf_alistado_dispositivo == dispositivo
        )
        propias.write({
            'x_gf_alistado_por': False,
            'x_gf_alistado_dispositivo': False,
            'x_gf_alistado_empleado': False,
            'x_gf_alistado_desde': False,
        })
        return True
