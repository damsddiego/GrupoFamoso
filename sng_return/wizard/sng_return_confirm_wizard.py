from odoo import api, fields, models


class SngReturnConfirmWizard(models.TransientModel):
    _name = "sng.return.confirm.wizard"
    _description = "Seleccionar almacén para devolución"

    return_id = fields.Many2one(
        "sng.return",
        string="Devolución",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="return_id.company_id",
        string="Compañía",
        readonly=True,
    )
    partner_id = fields.Many2one(
        related="return_id.partner_id",
        string="Cliente",
        readonly=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Almacén destino",
        required=True,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        string="Ubicación de recepción",
        compute="_compute_location_dest_id",
        readonly=True,
    )

    @api.depends("warehouse_id")
    def _compute_location_dest_id(self):
        for wizard in self:
            wizard.location_dest_id = wizard.return_id._get_return_destination_location(
                wizard.warehouse_id
            )

    def action_confirm(self):
        self.ensure_one()
        self.return_id._confirm_with_warehouse(self.warehouse_id)
        return {"type": "ir.actions.act_window_close"}
