# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RejectedInvoiceReplacementWizard(models.TransientModel):
    _name = "rejected.invoice.replacement.wizard"
    _description = "Wizard to Link Replacement Invoice"

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    rejected_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Documento Rechazado",
        required=True,
        readonly=True,
    )

    rejected_move_type = fields.Selection(
        related="rejected_invoice_id.move_type",
    )

    replacement_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Documento de Reemplazo",
        required=True,
        domain="['|', ('state_tributacion', '=', 'aceptado'), ('tipo_documento', '=', 'disabled'), ('id', '!=', rejected_invoice_id), ('move_type', '=', rejected_move_type), ('company_id', '=', company_id)]",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        related="rejected_invoice_id.company_id",
        readonly=True,
    )

    notes = fields.Text(string="Notas")

    # -------------------------------------------------------------------------
    # VALIDATION
    # -------------------------------------------------------------------------

    @api.constrains("replacement_invoice_id")
    def _check_replacement_valid(self):
        for wiz in self:
            if not wiz.replacement_invoice_id:
                continue

            repl = wiz.replacement_invoice_id

            # Must be accepted by Hacienda OR be a disabled electronic document
            if repl.state_tributacion != "aceptado" and repl.tipo_documento != "disabled":
                raise UserError(
                    _(
                        "La factura '%s' no está aceptada por Hacienda ni es un "
                        "Documento Electrónico Deshabilitado. Estado actual: %s"
                    )
                    % (
                        repl.name or repl.display_name,
                        dict(repl._fields["state_tributacion"].selection).get(
                            repl.state_tributacion, repl.state_tributacion
                        ),
                    )
                )

            # Must be same company
            if repl.company_id != wiz.rejected_invoice_id.company_id:
                raise UserError(
                    _(
                        "La factura de reemplazo debe pertenecer a la misma compañía "
                        "que la factura rechazada."
                    )
                )

            # Cannot be the same invoice
            if repl == wiz.rejected_invoice_id:
                raise UserError(_("Una factura no puede ser reemplazo de sí misma."))

            # Check if replacement invoice already replaces another invoice
            if repl.replaces_invoice_id and repl.replaces_invoice_id != wiz.rejected_invoice_id:
                raise UserError(
                    _(
                        "La factura '%s' ya está vinculada como reemplazo de '%s'. "
                        "Una factura solo puede reemplazar a una factura rechazada."
                    )
                    % (
                        repl.name or repl.display_name,
                        repl.replaces_invoice_id.name or repl.replaces_invoice_id.display_name,
                    )
                )

    # -------------------------------------------------------------------------
    # ACTION
    # -------------------------------------------------------------------------

    def action_link_replacement(self):
        self.ensure_one()

        if not self.replacement_invoice_id:
            raise UserError(_("Debe seleccionar una factura de reemplazo."))

        # Calculate next sequence number
        rejected = self.rejected_invoice_id
        next_seq = 1
        if rejected.rejected_invoice_history_ids:
            next_seq = max(rejected.rejected_invoice_history_ids.mapped("sequence")) + 1

        # Create history entry
        self.env["rejected.invoice.replacement.history"].create({
            "rejected_invoice_id": rejected.id,
            "replacement_invoice_id": self.replacement_invoice_id.id,
            "sequence": next_seq,
            "state": "linked",
            "is_current": True,
            "notes": self.notes or False,
        })

        return {"type": "ir.actions.act_window_close"}
