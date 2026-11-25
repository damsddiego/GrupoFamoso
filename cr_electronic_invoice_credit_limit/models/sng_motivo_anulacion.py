from odoo import fields, models


class SngMotivoAnulacion(models.Model):
    _name = "sng.motivo.anulacion"
    _description = "Motivo de anulación de factura"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Motivo", required=True)
    active = fields.Boolean(default=True)
    requiere_refactura = fields.Boolean(
        string="Requiere refactura",
        default=True,
        help="Con este motivo la factura anulada se vuelve a emitir. Mientras "
             "la factura sustituta no esté confirmada, la nota de crédito "
             "aparece como «Sin refactura» en el control de anulaciones.",
    )
