# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RejectedInvoiceReplacementHistory(models.Model):
    _name = "rejected.invoice.replacement.history"
    _description = "Rejected Invoice Replacement History"
    _order = "sequence, id"

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    rejected_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Documento Rechazado",
        required=True,
        ondelete="cascade",
        index=True,
        domain=[
            ("move_type", "in", ("out_invoice", "out_refund")),
            "|",
            ("state_tributacion", "=", "rechazado"),
            ("einvoice_had_rejection", "=", True),
        ],
        help="La factura o nota de crédito original rechazada por Hacienda.",
    )

    replacement_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Documento de Reemplazo",
        ondelete="set null",
        index=True,
        domain=[("move_type", "in", ("out_invoice", "out_refund"))],
        help="El documento que reemplaza al rechazado.",
    )

    sequence = fields.Integer(
        string="Intento #",
        required=True,
        default=1,
        help="Número secuencial del intento de reemplazo.",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("linked", "Vinculado"),
            ("accepted", "Aceptado por Hacienda"),
            ("rejected", "Rechazado por Hacienda"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado del Reemplazo",
        default="draft",
        required=True,
    )

    link_date = fields.Datetime(
        string="Fecha de Vinculación",
        default=lambda self: fields.Datetime.now(),
    )

    linked_by_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Vinculado por",
        default=lambda self: self.env.user,
    )

    is_current = fields.Boolean(
        string="Reemplazo Actual",
        default=False,
        index=True,
        help="Indica si este es el reemplazo activo actual.",
    )

    notes = fields.Text(string="Notas")

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        related="rejected_invoice_id.company_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------

    # Note: uniqueness of 'current' per rejected invoice is enforced
    # in code via _update_current_flag, not via SQL constraint,
    # because SQL unique would also block multiple False values.

    # -------------------------------------------------------------------------
    # ONCHANGE / VALIDATION
    # -------------------------------------------------------------------------

    @api.constrains("replacement_invoice_id", "rejected_invoice_id")
    def _check_not_self_reference(self):
        for rec in self:
            if (
                rec.replacement_invoice_id
                and rec.replacement_invoice_id == rec.rejected_invoice_id
            ):
                raise UserError(
                    _(
                        "Una factura no puede ser reemplazo de sí misma."
                    )
                )

    @api.constrains("replacement_invoice_id")
    def _check_replacement_is_accepted(self):
        for rec in self:
            if rec.replacement_invoice_id and rec.state != "draft":
                repl = rec.replacement_invoice_id
                if repl.state_tributacion != "aceptado" and repl.tipo_documento != "disabled":
                    raise UserError(
                        _(
                            "La factura de reemplazo '%s' debe estar 'Aceptada' por Hacienda "
                            "o ser un Documento Electrónico Deshabilitado. "
                            "Estado actual: %s"
                        )
                        % (
                            repl.name or repl.display_name,
                            dict(repl._fields["state_tributacion"].selection).get(
                                repl.state_tributacion, repl.state_tributacion
                            ),
                        )
                    )

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("skip_current_flag_update"):
            for rec in records:
                rec._update_current_flag()
                rec._sync_replacement_invoice()
                rec._post_chatter_messages()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_current_flag_update"):
            if "replacement_invoice_id" in vals or "is_current" in vals:
                for rec in self:
                    rec._update_current_flag()
                    rec._sync_replacement_invoice()
                    rec._post_chatter_messages()
        return res

    def unlink(self):
        for rec in self:
            if rec.replacement_invoice_id:
                rec.replacement_invoice_id.replaces_invoice_id = False
        return super(RejectedInvoiceReplacementHistory, self).unlink()

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _update_current_flag(self):
        """Ensure only the most recent history entry is marked as current."""
        self.ensure_one()
        if not self.rejected_invoice_id:
            return

        all_history = self.rejected_invoice_id.rejected_invoice_history_ids.sorted(
            key=lambda r: (r.sequence, r.id), reverse=True
        )

        if all_history:
            most_recent = all_history[0]
            to_set_current = all_history.filtered(
                lambda h: h.id == most_recent.id and not h.is_current
            )
            to_unset_current = all_history.filtered(
                lambda h: h.id != most_recent.id and h.is_current
            )
            if to_set_current:
                to_set_current.with_context(skip_current_flag_update=True).write(
                    {"is_current": True}
                )
            if to_unset_current:
                to_unset_current.with_context(skip_current_flag_update=True).write(
                    {"is_current": False}
                )

    def _sync_replacement_invoice(self):
        """Sync the replaces_invoice_id on the replacement invoice side."""
        self.ensure_one()
        if self.is_current and self.replacement_invoice_id:
            self.replacement_invoice_id.replaces_invoice_id = self.rejected_invoice_id
        elif not self.is_current and self.replacement_invoice_id:
            # If this is no longer current, check if another history entry
            # points to the same replacement invoice as current
            other = self.env["rejected.invoice.replacement.history"].search([
                ("id", "!=", self.id),
                ("replacement_invoice_id", "=", self.replacement_invoice_id.id),
                ("is_current", "=", True),
            ], limit=1)
            if not other:
                self.replacement_invoice_id.replaces_invoice_id = False

    def _post_chatter_messages(self):
        """Post messages to the chatter of both invoices."""
        self.ensure_one()
        if not self.replacement_invoice_id:
            return

        # Message on rejected invoice
        self.rejected_invoice_id.message_post(
            subject=_("Reemplazo de Factura Rechazada"),
            body=_(
                "<p>Intento de reemplazo #<strong>%(seq)d</strong> vinculado:</p>"
                "<ul>"
                "<li>Factura de reemplazo: <strong>%(repl)s</strong></li>"
                "<li>Clave electrónica reemplazo: %(clave)s</li>"
                "<li>Vinculado por: %(user)s</li>"
                "<li>Fecha: %(date)s</li>"
                "</ul>"
            )
            % {
                "seq": self.sequence,
                "repl": self.replacement_invoice_id.name or self.replacement_invoice_id.display_name,
                "clave": self.replacement_invoice_id.number_electronic or "N/A",
                "user": self.linked_by_user_id.name or "N/A",
                "date": self.link_date,
            },
        )

        # Message on replacement invoice
        self.replacement_invoice_id.message_post(
            subject=_("Vinculación con Factura Rechazada"),
            body=_(
                "<p>Esta factura ha sido vinculada como reemplazo de:</p>"
                "<ul>"
                "<li>Factura rechazada: <strong>%(rej)s</strong></li>"
                "<li>Clave electrónica rechazada: %(clave)s</li>"
                "<li>Intento #%(seq)d</li>"
                "</ul>"
            )
            % {
                "rej": self.rejected_invoice_id.name or self.rejected_invoice_id.display_name,
                "clave": self.rejected_invoice_id.number_electronic or "N/A",
                "seq": self.sequence,
            },
        )
