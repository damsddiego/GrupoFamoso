from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError


TAX_ADMIN_GROUP = "base.group_system"


def _m2m_result_ids(record, field_name, value):
    """Return the tax ids the relation would hold after writing ``value``.

    Returns ``None`` when the commands modify account.tax records themselves
    (create, update, delete) or cannot be interpreted; callers must treat
    ``None`` as a disallowed change.
    """
    if hasattr(value, "_name"):
        return set(value.ids)
    if not value:
        return set()

    result_ids = set(record[field_name].ids)
    for command in value:
        if isinstance(command, int):
            result_ids.add(command)
            continue
        if not isinstance(command, (tuple, list)) or not command:
            return None

        operation = command[0]
        if operation in (Command.CREATE, Command.UPDATE, Command.DELETE):
            return None
        if operation == Command.UNLINK:
            result_ids.discard(command[1])
        elif operation == Command.LINK:
            result_ids.add(command[1])
        elif operation == Command.CLEAR:
            result_ids.clear()
        elif operation == Command.SET:
            result_ids = set(command[2])
        else:
            return None

    return result_ids


class TaxEditLockMixin(models.AbstractModel):
    _name = "sng.tax.edit.lock.mixin"
    _description = "Bloqueo de edicion de impuestos"

    sng_tax_edit_allowed = fields.Boolean(
        string="Puede editar impuestos",
        compute="_compute_sng_tax_edit_allowed",
    )

    @api.depends_context("uid")
    def _compute_sng_tax_edit_allowed(self):
        allowed = self.env.su or self.env.user.has_group(TAX_ADMIN_GROUP)
        for record in self:
            record.sng_tax_edit_allowed = (
                allowed or record._sng_tax_edit_lock_exempt()
            )

    def _sng_tax_edit_lock_exempt(self):
        """Hook por registro: True si la linea queda fuera del bloqueo."""
        return False

    def _sng_tax_edit_is_admin(self):
        return self.env.su or self.env.user.has_group(TAX_ADMIN_GROUP)

    def _sng_tax_edit_error_message(self):
        return _(
            "Solamente un usuario del grupo Ajustes / Administrador "
            "puede cambiar los impuestos de una linea."
        )

    def _sng_check_tax_write(self, vals, field_name, allow_clear=False):
        if self.env.context.get("sng_tax_edit_lock_bypass"):
            return
        if field_name not in vals or self._sng_tax_edit_is_admin():
            return

        for record in self:
            if record._sng_tax_edit_lock_exempt():
                continue
            result_ids = _m2m_result_ids(record, field_name, vals[field_name])
            # Permitir no-ops: clientes que reenvian el valor sin cambiarlo.
            if result_ids is not None and result_ids == set(
                record[field_name].ids
            ):
                continue
            if allow_clear and result_ids == set():
                continue
            raise AccessError(record._sng_tax_edit_error_message())


class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _inherit = ["sale.order.line", "sng.tax.edit.lock.mixin"]

    def _sng_tax_edit_error_message(self):
        return _(
            "Solamente un usuario del grupo Ajustes / Administrador puede "
            "asignar un impuesto distinto al del producto. Un usuario normal "
            "solo puede quitar el impuesto de la linea (ventas sin documento "
            "electronico)."
        )

    @api.model_create_multi
    def create(self, vals_list):
        flagged_indexes = (
            []
            if self._sng_tax_edit_is_admin()
            else [i for i, vals in enumerate(vals_list) if "tax_id" in vals]
        )
        lines = super().create(vals_list)

        flagged = lines.browse(
            [lines[i].id for i in flagged_indexes]
        ).filtered(lambda line: not line.display_type)
        if flagged:
            requested = {line.id: line.tax_id for line in flagged}
            # El compute escribe tax_id internamente; se exime del chequeo
            # porque aqui solo se calcula el default para comparar.
            flagged.with_context(
                sng_tax_edit_lock_bypass=True
            )._compute_tax_id()
            offending = flagged.filtered(
                lambda line: requested[line.id]
                and line.tax_id != requested[line.id]
            )
            if offending:
                raise AccessError(offending._sng_tax_edit_error_message())
            # Quitar el impuesto si esta permitido: se restauran las lineas
            # pedidas explicitamente sin impuesto que el compute repoblo.
            for line in flagged:
                if not requested[line.id] and line.tax_id:
                    line.tax_id = requested[line.id]
        return lines

    def write(self, vals):
        self._sng_check_tax_write(vals, "tax_id", allow_clear=True)
        return super().write(vals)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _sng_tax_required_for_post(self):
        """La factura exige impuestos salvo documentos electronicos
        desactivados (en el documento o a nivel de compania)."""
        self.ensure_one()
        return (
            self.move_type in ("out_invoice", "out_refund")
            and self.tipo_documento != "disabled"
            and self.company_id.frm_ws_ambiente != "disabled"
        )

    def _sng_lines_missing_tax(self):
        self.ensure_one()
        # "Otros Cargos" e "IVA Devuelto" van sin impuesto por diseno de la
        # factura electronica (cr_electronic_invoice los trata aparte).
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
            and not line.tax_ids
            and line.product_id.categ_id.name != "Otros Cargos"
            and line.product_id.name != "IVA Devuelto"
        )

    def action_post(self):
        for move in self:
            if not move._sng_tax_required_for_post():
                continue
            lines_missing = move._sng_lines_missing_tax()
            if lines_missing:
                raise UserError(
                    _(
                        "No se puede confirmar la factura %(move)s: el tipo "
                        "de documento no es \"Documentos electronicos "
                        "desactivados\" y las siguientes lineas no tienen "
                        "impuesto asignado:\n%(lines)s",
                        move=move.display_name,
                        lines="\n".join(
                            "- %s"
                            % (line.product_id.display_name or line.name)
                            for line in lines_missing
                        ),
                    )
                )
        return super().action_post()


class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = ["account.move.line", "sng.tax.edit.lock.mixin"]

    # No se bloquea create(): la importacion de documentos electronicos
    # (cr_electronic_invoice) crea lineas con tax_ids explicitos y debe
    # seguir funcionando. La vista deja el campo readonly para no-admins.

    @api.depends("move_id.tipo_documento")
    def _compute_sng_tax_edit_allowed(self):
        super()._compute_sng_tax_edit_allowed()

    def _sng_tax_edit_lock_exempt(self):
        # Facturas con documentos electronicos desactivados no se reportan
        # a Hacienda; ahi si se permite quitar o cambiar el impuesto.
        return self.move_id.tipo_documento == "disabled"

    def write(self, vals):
        self._sng_check_tax_write(vals, "tax_ids")
        return super().write(vals)
