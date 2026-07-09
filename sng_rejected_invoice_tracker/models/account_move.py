# -*- coding: utf-8 -*-
import base64
import logging
import xml.etree.ElementTree as ET

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    _REJECTED_MOVE_TYPES = ("out_invoice", "out_refund")

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    rejected_invoice_history_ids = fields.One2many(
        comodel_name="rejected.invoice.replacement.history",
        inverse_name="rejected_invoice_id",
        string="Historial de Reemplazos",
        help="Historial completo de intentos de reemplazo para esta factura rechazada.",
    )

    replaced_by_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Reemplazada por",
        compute="_compute_replacement_fields",
        store=False,
        help="La factura de reemplazo actual (más reciente).",
    )

    replaces_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Reemplaza a",
        index=True,
        help="Si esta factura es un reemplazo, apunta a la factura rechazada original.",
    )

    fe_replacement_status = fields.Selection(
        selection=[
            ("no_aplica", "No Aplica"),
            ("pendiente", "Pendiente de Reemplazo"),
            ("reemplazada", "Reemplazada"),
        ],
        string="Estado de Reemplazo",
        compute="_compute_replacement_fields",
        store=True,
    )

    fe_replacement_attempt_count = fields.Integer(
        string="Intentos de Reemplazo",
        compute="_compute_replacement_fields",
    )

    fe_rejection_detail = fields.Text(
        string="Motivo de Rechazo Hacienda",
        compute="_compute_fe_rejection_detail",
        store=True,
        copy=False,
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends("xml_respuesta_tributacion", "state_tributacion", "einvoice_had_rejection")
    def _compute_fe_rejection_detail(self):
        for move in self:
            move.fe_rejection_detail = False
            if not move.xml_respuesta_tributacion:
                continue
            if not (
                move.move_type in self._REJECTED_MOVE_TYPES
                and (move.state_tributacion == "rechazado" or move.einvoice_had_rejection)
            ):
                continue
            try:
                xml_bytes = base64.b64decode(move.xml_respuesta_tributacion)
                root = ET.fromstring(xml_bytes)
                for el in root.iter():
                    local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
                    if local == "DetalleMensaje" and el.text:
                        move.fe_rejection_detail = el.text.strip()
                        break
            except Exception as e:
                _logger.warning("Could not parse rejection detail for move %s: %s", move.id, e)

    @api.depends(
        "state_tributacion",
        "einvoice_had_rejection",
        "rejected_invoice_history_ids",
        "rejected_invoice_history_ids.is_current",
        "rejected_invoice_history_ids.replacement_invoice_id",
    )
    def _compute_replacement_fields(self):
        for move in self:
            move.fe_replacement_status = "no_aplica"
            move.replaced_by_invoice_id = False
            move.fe_replacement_attempt_count = 0

            is_rejected = (
                move.move_type in self._REJECTED_MOVE_TYPES
                and (
                    move.state_tributacion == "rechazado"
                    or move.einvoice_had_rejection
                )
            )

            if not is_rejected:
                continue

            history = move.rejected_invoice_history_ids
            move.fe_replacement_attempt_count = len(history)

            current = history.filtered(lambda h: h.is_current)
            if current and current.replacement_invoice_id:
                move.replaced_by_invoice_id = current.replacement_invoice_id
                move.fe_replacement_status = "reemplazada"
            else:
                move.fe_replacement_status = "pendiente"

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    def action_create_replacement_invoice(self):
        """
        Create a copy of the rejected invoice as a replacement draft.
        Adds a history entry linking the rejected invoice to the new one.
        Returns an action opening the new invoice form.
        """
        self.ensure_one()

        # Validate that this is a rejected invoice
        if not (
            self.move_type in self._REJECTED_MOVE_TYPES
            and (self.state_tributacion == "rechazado" or self.einvoice_had_rejection)
        ):
            raise UserError(
                _(
                    "Solo se pueden crear reemplazos para documentos de cliente rechazados por Hacienda."
                )
            )

        # Prepare default values for the copy.
        # Clear all FE state fields so a fresh electronic document is generated.
        # For credit notes (out_refund), the reference fields (invoice_id,
        # reference_code_id, reference_document_id, not_loaded_invoice*) are
        # business data that cr_electronic_invoice uses to build the XML
        # InformacionReferencia block — they must be carried over unchanged.
        default_vals = {
            "name": "/",
            "number_electronic": False,
            "sequence": False,
            "date_issuance": False,
            "state_tributacion": False,
            "einvoice_had_rejection": False,
            "xml_comprobante": False,
            "fname_xml_comprobante": False,
            "xml_respuesta_tributacion": False,
            "fname_xml_respuesta_tributacion": False,
            "state_email": False,
            "error_count": 0,
            "electronic_invoice_return_message": False,
            "consecutive_number_receiver": False,
            "replaces_invoice_id": self.id,
        }

        if self.move_type == "out_refund":
            # Preserve reference data required for the NC XML generation
            default_vals.update({
                "invoice_id": self.invoice_id.id or False,
                "reference_code_id": self.reference_code_id.id or False,
                "reference_document_id": self.reference_document_id.id or False,
                "not_loaded_invoice": self.not_loaded_invoice or False,
                "not_loaded_invoice_date": self.not_loaded_invoice_date or False,
            })

        new_invoice = self.copy(default=default_vals)

        if not new_invoice:
            raise UserError(
                _("No se pudo crear la factura de reemplazo. Intente nuevamente.")
            )

        # Calculate next sequence number for history
        next_seq = 1
        if self.rejected_invoice_history_ids:
            next_seq = max(self.rejected_invoice_history_ids.mapped("sequence")) + 1

        # Create history entry
        self.env["rejected.invoice.replacement.history"].create({
            "rejected_invoice_id": self.id,
            "replacement_invoice_id": new_invoice.id,
            "sequence": next_seq,
            "state": "draft",
            "is_current": True,
        })

        _logger.info(
            "Replacement invoice %s created for rejected invoice %s (attempt #%d)",
            new_invoice.name or new_invoice.id,
            self.name or self.id,
            next_seq,
        )

        # Return action to open the new invoice
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": new_invoice.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": {"default_move_type": self.move_type},
        }

    def action_open_link_replacement_wizard(self):
        """
        Open the wizard to manually link an existing accepted invoice
        as a replacement for this rejected invoice.
        """
        self.ensure_one()

        if not (
            self.move_type in self._REJECTED_MOVE_TYPES
            and (self.state_tributacion == "rechazado" or self.einvoice_had_rejection)
        ):
            raise UserError(
                _(
                    "Solo se pueden vincular reemplazos para documentos de cliente rechazados por Hacienda."
                )
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": "rejected.invoice.replacement.wizard",
            "view_mode": "form",
            "view_id": self.env.ref(
                "sng_rejected_invoice_tracker.view_rejected_invoice_replacement_wizard_form"
            ).id,
            "target": "new",
            "context": {
                "default_rejected_invoice_id": self.id,
            },
        }

    def action_view_replacement_history(self):
        """Open a list view of the replacement history for this invoice."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "rejected.invoice.replacement.history",
            "view_mode": "list,form",
            "domain": [("rejected_invoice_id", "=", self.id)],
            "context": {"default_rejected_invoice_id": self.id},
            "name": _("Historial de Reemplazos - %s") % (self.name or self.display_name),
        }

    def action_transfer_payments_to_replacement(self):
        """
        Unreconcile payments from this rejected invoice and reconcile them
        against the current replacement invoice.
        Only payment journal entries (origin_payment_id) are moved;
        reconciliations from other invoices or credit notes are left untouched.
        """
        self.ensure_one()

        if not self.replaced_by_invoice_id:
            raise UserError(_("No hay factura de reemplazo vinculada a este documento."))

        replacement = self.replaced_by_invoice_id

        if replacement.state != "posted":
            raise UserError(
                _("La factura de reemplazo '%s' debe estar publicada para recibir pagos.")
                % replacement.display_name
            )

        # Receivable lines on the original (rejected) invoice
        original_receivable = self.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            and (l.matched_debit_ids or l.matched_credit_ids)
        )
        if not original_receivable:
            raise UserError(_("Esta factura no tiene pagos asociados para trasladar."))

        # Gather only the partial reconciles that come from payment journal entries
        payment_partials = self.env["account.partial.reconcile"]
        payment_amls = self.env["account.move.line"]

        for partial in original_receivable.mapped("matched_debit_ids"):
            if partial.debit_move_id.move_id.origin_payment_id:
                payment_partials |= partial
                payment_amls |= partial.debit_move_id

        for partial in original_receivable.mapped("matched_credit_ids"):
            if partial.credit_move_id.move_id.origin_payment_id:
                payment_partials |= partial
                payment_amls |= partial.credit_move_id

        if not payment_partials:
            raise UserError(
                _("No se encontraron pagos registrados para trasladar. "
                  "Verifique que los pagos hayan sido aplicados a esta factura.")
            )

        # --- Unreconcile from rejected invoice ---
        payment_partials.unlink()

        # --- Re-reconcile against replacement invoice ---
        replacement_receivable = replacement.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            and not l.reconciled
        )
        if not replacement_receivable:
            raise UserError(
                _("La factura de reemplazo '%s' no tiene saldo pendiente para aplicar pagos.")
                % replacement.display_name
            )

        (replacement_receivable | payment_amls).reconcile()

        payment_count = len(payment_amls.mapped("move_id.origin_payment_id"))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pagos Trasladados"),
                "message": _(
                    "%d pago(s) trasladados exitosamente a la factura de reemplazo '%s'."
                ) % (payment_count, replacement.display_name),
                "type": "success",
                "sticky": False,
            },
        }

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------

    def write(self, vals):
        res = super().write(vals)
        if "state_tributacion" in vals:
            new_state = vals["state_tributacion"]
            history = self.env["rejected.invoice.replacement.history"].search([
                ("replacement_invoice_id", "in", self.ids),
            ])
            if history:
                state_map = {
                    "aceptado": "accepted",
                    "rechazado": "rejected",
                }
                mapped_state = state_map.get(new_state)
                if mapped_state:
                    history.with_context(skip_current_flag_update=True).write({
                        "state": mapped_state,
                    })
        return res

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------

    @api.constrains("replaces_invoice_id")
    def _check_replaces_invoice_cycle(self):
        for move in self:
            if move.replaces_invoice_id:
                if move.replaces_invoice_id == move:
                    raise UserError(_("Una factura no puede reemplazarse a sí misma."))
                if move.replaces_invoice_id.replaced_by_invoice_id == move:
                    # This is fine, it's the bidirectional link
                    pass

    @api.constrains("rejected_invoice_history_ids")
    def _check_history_company_consistency(self):
        for move in self:
            for hist in move.rejected_invoice_history_ids:
                if (
                    hist.replacement_invoice_id
                    and hist.replacement_invoice_id.company_id != move.company_id
                ):
                    raise UserError(
                        _(
                            "La factura de reemplazo '%s' debe pertenecer a la misma compañía."
                        )
                        % hist.replacement_invoice_id.name
                    )
