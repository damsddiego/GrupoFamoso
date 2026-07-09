# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SngSalesRoute(models.Model):
    _name = "sng.sales.route"
    _description = "Ruta / Territorio de Venta"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(string="Nombre", required=True, translate=True)
    code = fields.Char(string="Código", index=True)
    active = fields.Boolean(string="Activo", default=True)
    sequence = fields.Integer(string="Secuencia", default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        index=True,
        default=lambda self: self.env.company,
        help="Si se deja vacío, la ruta queda disponible para todas las compañías.",
    )
    salesperson_id = fields.Many2one(
        "res.partner",
        string="Vendedor de referencia",
        domain="[('is_salesperson', '=', True)]",
        check_company=True,
        help="Referencia informativa. No asigna vendedores ni modifica comisiones.",
    )
    note = fields.Text(string="Notas")

    _sql_constraints = [
        (
            "name_company_uniq",
            "unique(name, company_id)",
            "El nombre de la ruta debe ser único por compañía.",
        ),
    ]

    @api.onchange("name")
    def _onchange_name_set_code(self):
        if self.name and not self.code:
            self.code = (self.name or "").strip().upper().replace(" ", "_")[:32]

    @api.constrains("code", "company_id")
    def _check_code_company_unique(self):
        for route in self.filtered("code"):
            domain = [
                ("id", "!=", route.id),
                ("code", "=", route.code),
                ("company_id", "=", route.company_id.id if route.company_id else False),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    _("El código de la ruta debe ser único por compañía.")
                )
