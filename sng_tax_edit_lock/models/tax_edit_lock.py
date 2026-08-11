from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError


TAX_ADMIN_GROUP = "base.group_system"


def _m2m_value_changes(record, field_name, value):
    """Return whether an x2many command changes the current relation.

    Allowing no-op writes avoids false positives from clients that resend an
    unchanged value. Commands that create, update or delete an account.tax are
    always considered a change and are therefore rejected for non-admins.
    """
    current_ids = set(record[field_name].ids)

    if hasattr(value, "_name"):
        return set(value.ids) != current_ids
    if not value:
        return bool(current_ids)

    result_ids = set(current_ids)
    for command in value:
        if isinstance(command, int):
            result_ids.add(command)
            continue
        if not isinstance(command, (tuple, list)) or not command:
            return True

        operation = command[0]
        if operation in (Command.CREATE, Command.UPDATE, Command.DELETE):
            return True
        if operation == Command.UNLINK:
            result_ids.discard(command[1])
        elif operation == Command.LINK:
            result_ids.add(command[1])
        elif operation == Command.CLEAR:
            result_ids.clear()
        elif operation == Command.SET:
            result_ids = set(command[2])
        else:
            return True

    return result_ids != current_ids


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
            record.sng_tax_edit_allowed = allowed

    def _sng_tax_edit_is_admin(self):
        return self.env.su or self.env.user.has_group(TAX_ADMIN_GROUP)

    def _sng_check_tax_write(self, vals, field_name):
        if field_name not in vals or self._sng_tax_edit_is_admin():
            return

        if any(
            _m2m_value_changes(record, field_name, vals[field_name])
            for record in self
        ):
            raise AccessError(
                _(
                    "Solamente un usuario del grupo Ajustes / Administrador "
                    "puede cambiar los impuestos de una linea."
                )
            )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        for order in self:
            lines_without_tax = order.order_line.filtered(
                lambda line: not line.display_type
                and line.product_type != "combo"
                and not line.tax_id
            )
            if lines_without_tax:
                raise UserError(
                    _(
                        "No se puede confirmar el pedido %(order)s: las "
                        "siguientes lineas no tienen impuesto asignado:\n%(lines)s",
                        order=order.display_name,
                        lines="\n".join(
                            "- %s" % (line.product_id.display_name or line.name)
                            for line in lines_without_tax
                        ),
                    )
                )
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _inherit = ["sale.order.line", "sng.tax.edit.lock.mixin"]

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
            flagged._compute_tax_id()
            if any(line.tax_id != requested[line.id] for line in flagged):
                raise AccessError(
                    _(
                        "Solamente un usuario del grupo Ajustes / "
                        "Administrador puede asignar manualmente impuestos "
                        "distintos a los del producto."
                    )
                )
        return lines

    def write(self, vals):
        self._sng_check_tax_write(vals, "tax_id")
        return super().write(vals)


class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = ["account.move.line", "sng.tax.edit.lock.mixin"]

    # No se bloquea create(): la importacion de documentos electronicos
    # (cr_electronic_invoice) crea lineas con tax_ids explicitos y debe
    # seguir funcionando. La vista deja el campo readonly para no-admins.

    def write(self, vals):
        self._sng_check_tax_write(vals, "tax_ids")
        return super().write(vals)
