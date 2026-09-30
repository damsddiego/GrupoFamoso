# -*- coding: utf-8 -*-
from odoo import models
from odoo.osv import expression

# Clave de contexto con la que una app pide excluir las ubicaciones marcadas.
# Sin ella el cálculo de Odoo queda intacto: la web, las reservas, el
# reabastecimiento y la valoración siguen viendo todo el stock.
CLAVE_CONTEXTO = 'sng_excluir_no_disponible'


def cambiar_campo(dominio, origen, destino):
    """Reescribe las hojas de un dominio de `origen` (o `origen.x`) a `destino`.

    Odoo arma el alcance de un almacén sobre el campo `location_id`; con esto
    se obtiene el mismo alcance aplicado al destino de los movimientos. Los
    operadores y las hojas especiales (p. ej. FALSE_LEAF) no se tocan.
    """
    resultado = []
    for termino in dominio:
        if (isinstance(termino, (list, tuple)) and len(termino) == 3
                and isinstance(termino[0], str)
                and (termino[0] == origen or termino[0].startswith(origen + '.'))):
            resultado.append((destino + termino[0][len(origen):], termino[1], termino[2]))
        else:
            resultado.append(termino)
    return resultado


def negar(dominio):
    """NOT de un dominio completo."""
    return ['!'] + expression.normalize_domain(dominio)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_domain_locations_new(self, location_ids):
        """Descuenta las ubicaciones "No disponible para venta" si se pidió.

        Why: al consultar por almacén Odoo suma todo lo que cuelga de él, y
        almacenes como Principal tienen al lado de Existencias ubicaciones
        como "Malo" que las entregas nunca toman. Los vendedores veían ese
        stock como disponible.

        Se trabaja sobre el resultado de super() y no sobre location_ids,
        para encadenarse con cualquier otro módulo que ya recorte las
        ubicaciones (p. ej. stock_warehouse_security) sin depender del orden
        de carga. Las marcadas no se pueden quitar de location_ids porque
        casi siempre son hijas de las raíces que llegan (la vista del almacén).
        """
        dominios = super()._get_domain_locations_new(location_ids)
        if not self.env.context.get(CLAVE_CONTEXTO):
            return dominios

        excluidas = self.env['stock.location'].sudo().with_context(active_test=False).search(
            [('sng_no_disponible_venta', '=', True)])
        if not excluidas:
            return dominios

        # El dominio de quants es "el origen está en el alcance"; Odoo usa el
        # mismo campo (location_id) en stock.quant y en stock.move.
        origen_en_alcance = dominios[0]
        destino_en_alcance = cambiar_campo(origen_en_alcance, 'location_id', 'location_dest_id')

        origen_vendible = expression.AND([
            origen_en_alcance,
            negar([('location_id', 'child_of', excluidas.ids)]),
        ])
        destino_vendible = expression.AND([
            destino_en_alcance,
            negar([('location_dest_id', 'child_of', excluidas.ids)]),
        ])

        # Se reconstruyen los tres dominios con el alcance "vendible", en vez
        # de solo restringir los de super(): así un movimiento de Malo a
        # Existencias cuenta como entrada, y uno de Existencias a Malo como
        # salida, que es lo que son desde el punto de vista de la venta.
        return (
            origen_vendible,
            expression.AND([destino_vendible, negar(origen_vendible)]),
            expression.AND([origen_vendible, negar(destino_vendible)]),
        )
