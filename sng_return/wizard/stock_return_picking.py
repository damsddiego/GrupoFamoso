from odoo import models

# Valores de la recepcion que la devolucion de cliente decide al confirmar.
SNG_RETURN_PICKING_DEFAULTS = ("picking_type_id", "location_dest_id", "sng_return_id")


class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def _prepare_picking_default_values(self):
        vals = super()._prepare_picking_default_values()
        # Devolucion de cliente (sng.return): la recepcion nace con el tipo de
        # operacion y el destino del almacen elegido, y ligada a la devolucion.
        defaults = self.env.context.get("sng_return_picking_defaults") or {}
        vals.update({
            key: defaults[key] for key in SNG_RETURN_PICKING_DEFAULTS if key in defaults
        })
        return vals
