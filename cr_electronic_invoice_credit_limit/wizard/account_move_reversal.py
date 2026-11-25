from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    sng_control_nc = fields.Boolean(compute="_compute_sng_control_nc")
    sng_tiene_entrega = fields.Boolean(compute="_compute_sng_control_nc")
    sng_pregunta_devolucion = fields.Boolean(compute="_compute_sng_pregunta_devolucion")
    sng_politica_devolucion = fields.Selection(
        related="reference_code_id.sng_politica_devolucion",
    )
    sng_codigo_referencia = fields.Char(related="reference_code_id.code")
    sng_devuelve_mercaderia = fields.Selection(
        [
            ("no", "No, el cliente se queda con la mercadería"),
            ("si", "Sí, la mercadería regresa a bodega"),
        ],
        string="¿La mercadería regresa a bodega?",
        compute="_compute_sng_devuelve_mercaderia",
        store=True,
        readonly=False,
    )
    sng_return_reason_id = fields.Many2one(
        "sng.return.reason",
        string="Motivo de la devolución",
    )
    sng_motivo_anulacion_id = fields.Many2one(
        "sng.motivo.anulacion",
        string="Motivo de anulación",
    )

    @api.depends("move_ids")
    def _compute_sng_control_nc(self):
        for wizard in self:
            moves = wizard.move_ids
            # El control aplica a facturas de cliente; lo demas sigue el
            # asistente estandar sin cambios.
            wizard.sng_control_nc = bool(moves) and all(
                move.move_type == "out_invoice" for move in moves
            )
            wizard.sng_tiene_entrega = wizard.sng_control_nc and any(
                moves.mapped("has_stock_delivery")
            )

    @api.depends("sng_control_nc", "sng_tiene_entrega", "sng_politica_devolucion")
    def _compute_sng_pregunta_devolucion(self):
        for wizard in self:
            wizard.sng_pregunta_devolucion = wizard.sng_control_nc and (
                wizard.sng_tiene_entrega or wizard.sng_politica_devolucion == "devuelve"
            )

    @api.depends("reference_code_id", "move_ids")
    def _compute_sng_devuelve_mercaderia(self):
        respuestas = {"devuelve": "si", "no_devuelve": "no"}
        for wizard in self:
            # Al cambiar a un codigo que pregunta, la respuesta queda vacia:
            # el usuario debe elegirla, no heredar la del codigo anterior.
            wizard.sng_devuelve_mercaderia = wizard.sng_control_nc and respuestas.get(
                wizard.sng_politica_devolucion, False
            )

    def _sng_respuesta_devolucion(self):
        """Respuesta vigente: la fija el codigo o la da el usuario."""
        self.ensure_one()
        if not self.sng_control_nc:
            return False
        politica = self.sng_politica_devolucion
        if politica == "devuelve":
            return "si"
        if politica == "no_devuelve":
            return "no"
        return self.sng_devuelve_mercaderia

    def _prepare_default_reversal(self, move):
        default_values = super()._prepare_default_reversal(move)
        if move.move_type == "out_invoice":
            default_values["sng_motivo_anulacion_id"] = self.sng_motivo_anulacion_id.id
        return default_values

    def reverse_moves(self, is_modify=False):
        self.ensure_one()
        if self.sng_control_nc:
            respuesta = self._sng_respuesta_devolucion()
            if respuesta == "si":
                return self._sng_solicitar_devolucion()
            # Solicitar la devolucion no crea nota de credito; lo demas si.
            self.env["account.move"]._sng_check_puede_crear_nota_credito()
            if self.sng_tiene_entrega and not respuesta:
                raise UserError(_(
                    "Indique si la mercadería regresa a bodega antes de crear la "
                    "nota de crédito."
                ))
        return super().reverse_moves(is_modify=is_modify)

    def modify_moves(self):
        self.ensure_one()
        if any(move.move_type == "out_invoice" for move in self.move_ids):
            return self._sng_anular_y_refacturar()
        return super().modify_moves()

    def _sng_solicitar_devolucion(self):
        """La mercaderia regresa: el camino es Devoluciones, no la NC directa."""
        self.ensure_one()
        if len(self.move_ids) != 1:
            raise UserError(_("Solicite la devolución de una factura a la vez."))
        if not self.sng_return_reason_id:
            raise UserError(_("Indique el motivo de la devolución."))
        if not self.env.user.has_group("sng_return.group_sng_return_user"):
            raise AccessError(_(
                "Para solicitar una devolución necesita el permiso «Usuario de "
                "Devoluciones». Pídalo a su administrador o solicite la devolución "
                "a quien ya lo tiene."
            ))
        customer_return = self.env["sng.return"]._crear_desde_factura(
            self.move_ids, self.sng_return_reason_id, notas=self.reason,
        )
        return {
            "name": _("Devolución de cliente"),
            "type": "ir.actions.act_window",
            "res_model": "sng.return",
            "res_id": customer_return.id,
            "view_mode": "form",
            "target": "current",
        }

    def _sng_anular_y_refacturar(self):
        """Anula la factura con una NC código 01 y abre su factura sustituta.

        Cada documento sale de su proceso normal: la NC la crea el asistente
        estándar y se confirma con action_post (el botón estándar «Revertir y
        crear factura» la confirma con _post directo y se salta el
        comprobante electrónico), que además la aplica a la factura; la
        factura nueva queda en borrador.
        """
        self.ensure_one()
        invoice = self.move_ids
        if len(invoice) != 1 or invoice.move_type != "out_invoice":
            raise UserError(_("Anule y refacture una factura de cliente a la vez."))
        if not self.sng_motivo_anulacion_id:
            raise UserError(_("Indique el motivo de anulación."))
        code = self.env["reference.code"].search([("code", "=", "01")], limit=1)
        if not code:
            raise UserError(_(
                "No existe el código de referencia 01 (Anula documento de referencia)."
            ))
        # La mercaderia se queda con el cliente: no hay devolucion.
        self.write({"reference_code_id": code.id, "sng_devuelve_mercaderia": "no"})

        action = self.reverse_moves(is_modify=False)
        credit_note = self.new_move_ids
        # Confirmar la NC la envia a Hacienda y eso no se deshace: la factura
        # sustituta se crea antes, para que cualquier error salga cuando todo
        # se puede revertir todavia.
        sustituta = credit_note._sng_crear_factura_sustituta(
            self._modify_default_reverse_values(invoice)
        )
        post_action = credit_note.action_post()
        if credit_note.state != "posted":
            # La confirmacion pide un paso adicional al usuario; la NC y su
            # sustituta quedan en borrador, ya enlazadas.
            return post_action or action

        # Al confirmarse, el propio Odoo aplica la NC a la factura que
        # revierte (account.move._post, _reconcile_reversed_moves).
        self.new_move_ids = sustituta
        return {
            "name": _("Factura sustituta"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": sustituta.id,
            "view_mode": "form",
            "context": {"default_move_type": sustituta.move_type},
        }
