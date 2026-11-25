from odoo import api, fields, models

# Códigos que nunca mueven inventario: corrigen monto o son financieros.
CODIGOS_SIN_DEVOLUCION = ("02", "09", "10", "12")
# Devolución de mercancía: la nota de crédito solo nace de Devoluciones.
CODIGOS_CON_DEVOLUCION = ("06",)


class ReferenceCode(models.Model):
    _inherit = "reference.code"

    sng_politica_devolucion = fields.Selection(
        [
            ("preguntar", "Preguntar al usuario"),
            ("devuelve", "La mercadería regresa (solo desde Devoluciones)"),
            ("no_devuelve", "No mueve inventario"),
        ],
        string="Devolución de mercadería",
        compute="_compute_sng_politica_devolucion",
        store=True,
        readonly=False,
        help="Define si una nota de crédito de cliente con este código puede "
             "traer mercadería de vuelta a bodega. Se propone según el código "
             "y se puede ajustar.",
    )

    @api.depends("code")
    def _compute_sng_politica_devolucion(self):
        for record in self:
            if record.code in CODIGOS_CON_DEVOLUCION:
                record.sng_politica_devolucion = "devuelve"
            elif record.code in CODIGOS_SIN_DEVOLUCION:
                record.sng_politica_devolucion = "no_devuelve"
            else:
                record.sng_politica_devolucion = "preguntar"
