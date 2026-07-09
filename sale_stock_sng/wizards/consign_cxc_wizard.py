# wizards/consign_cxc_wizard.py
from odoo import api, fields, models
from odoo.exceptions import UserError
from datetime import date


class ConsignCxcWizard(models.TransientModel):
    _name = "consign.cxc.wizard"
    _description = "Wizard Reporte Consignaciones y CxC"

    date_from = fields.Date(string="Fecha desde")
    date_to = fields.Date(string="Fecha hasta", required=True, default=fields.Date.context_today)

    location_ids = fields.Many2many(
        "stock.location",
        string="Bodegas (solo internas)",
        domain=[("usage", "=", "internal")],
        help="Si no seleccionas ninguna, se incluirán todas las ubicaciones internas."
    )

    user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        help="Si el vendedor tiene partner.sale_location_id, se llenan por defecto las bodegas."
    )

    @api.onchange("user_id")
    def _onchange_user_id_fill_locations(self):
        """
        Si hay vendedor seleccionado:
          - Buscar todos los contactos (clientes) con ese user_id
          - Tomar sus sale_location_id que sean internas
          - Rellenar location_ids con el conjunto único de esas ubicaciones
        Si no hay vendedor: no alterar location_ids (permite selección manual).
        """
        if not self.user_id:
            return

        partners = self.env["res.partner"].search([
            ("user_id", "=", self.user_id.id),
            ("sale_location_id", "!=", False),
        ])

        loc_ids = partners.mapped("sale_location_id").ids
        # Asignar el conjunto de ubicaciones (únicas)
        self.location_ids = [(6, 0, loc_ids)]

    def _get_date_from_effective(self):
        # Si no se definió fecha desde, tomar un origen muy antiguo
        return self.date_from or date(1970, 1, 1)

    def action_print(self):
        if not self.date_to:
            raise UserError("Debes indicar la fecha hasta.")
        if self.date_from and self.date_from > self.date_to:
            raise UserError("La fecha desde no puede ser mayor que la fecha hasta.")
        # OJO: usa el external id REAL que pusiste en el XML
        return self.env.ref("sale_stock_sng.consign_cxc_report_xlsx_action").report_action(self)
