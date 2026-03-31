from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class SngReturn(models.Model):
    _name = "sng.return"
    _description = "Devolucion de Cliente"
    _order = "date_request desc, id desc"

    name = fields.Char(
        string="Numero",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nuevo"),
    )
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        domain="[('customer_rank', '>', 0)]",
    )
    date_request = fields.Datetime(
        string="Fecha",
        required=True,
        default=fields.Datetime.now,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsable",
        required=True,
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        required=True,
        default="draft",
        copy=False,
    )
    reason_id = fields.Many2one(
        "sng.return.reason",
        string="Motivo",
        required=True,
    )
    notes = fields.Text(string="Notas")
    line_ids = fields.One2many(
        "sng.return.line",
        "return_id",
        string="Productos",
    )
    line_count = fields.Integer(
        string="Lineas",
        compute="_compute_totals",
    )
    total_qty = fields.Float(
        string="Cantidad Total",
        compute="_compute_totals",
        digits="Product Unit of Measure",
    )
    credit_note_ids = fields.Many2many(
        "account.move",
        string="Notas de Crédito",
        compute="_compute_credit_note_count",
    )
    credit_note_count = fields.Integer(
        string="Cant. NC",
        compute="_compute_credit_note_count",
    )

    def _compute_credit_note_count(self):
        for record in self:
            records = self.env["account.move"].search([
                ("invoice_origin", "=", record.name),
                ("move_type", "=", "out_refund")
            ])
            record.credit_note_ids = records
            record.credit_note_count = len(records)

    @api.depends("line_ids.quantity")
    def _compute_totals(self):
        for record in self:
            record.line_count = len(record.line_ids)
            record.total_qty = sum(record.line_ids.mapped("quantity"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code("sng.return") or _("Nuevo")
        return super().create(vals_list)

    def _check_supervisor_access(self):
        if not self.env.user.has_group("sng_return.group_sng_return_supervisor"):
            raise AccessError(_("No tiene permisos para confirmar o cancelar devoluciones."))

    def write(self, vals):
        if not self.env.user.has_group("sng_return.group_sng_return_supervisor"):
            if "state" in vals and vals["state"] != "draft":
                raise AccessError(_("No tiene permisos para cambiar el estado de la devolucion."))
            for record in self:
                if record.state != "draft":
                    raise AccessError(_("Solo puede modificar devoluciones en estado borrador."))
        return super().write(vals)

    def action_confirm(self):
        self._check_supervisor_access()
        for record in self:
            if not record.line_ids:
                raise UserError(_("Debe agregar al menos un producto a devolver."))
            for line in record.line_ids:
                line._validate_return_quantity()
            record.state = "confirmed"

    def action_cancel(self):
        self._check_supervisor_access()
        self.state = "cancelled"

    def action_set_to_draft(self):
        self._check_supervisor_access()
        self.state = "draft"

    def action_view_history(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Debe seleccionar un cliente antes de consultar el historial."))
        wizard_model = self.env["sng.return.history.wizard"]
        wizard = wizard_model.create({
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "return_id": self.id,
            "history_line_ids": wizard_model._build_history_commands(
                self.partner_id.id,
                False,
                self.company_id.id,
            ),
        })
        return {
            "name": _("Historial de ventas facturadas"),
            "type": "ir.actions.act_window",
            "res_model": "sng.return.history.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_generate_credit_note(self):
        self.ensure_one()
        if self.state != "confirmed":
            raise UserError(_("La devolución debe estar confirmada para generar la nota de crédito."))
        
        # Agrupar líneas por factura para crear una NC por cada factura original si es necesario
        # o una sola NC global si se prefiere. Por estándar de CR, suele ser 1 a 1 con la factura.
        lines_with_invoice = self.line_ids.filtered(lambda l: l.invoice_id)
        if not lines_with_invoice:
            raise UserError(_("Ninguna línea tiene una factura asociada para generar la nota de crédito."))

        invoices = lines_with_invoice.mapped("invoice_id")
        created_moves = self.env["account.move"]

        for invoice in invoices:
            return_lines = lines_with_invoice.filtered(lambda l: l.invoice_id == invoice)
            
            # Valores base para la NC
            move_vals = {
                "move_type": "out_refund",
                "partner_id": self.partner_id.id,
                "invoice_origin": self.name,
                "company_id": self.company_id.id,
                "reversed_entry_id": invoice.id,
                # Campos específicos de l10n_cr (basados en análisis previo)
                "tipo_documento": "NC",
                "reference_code_id": self.env["reference.code"].search([("code", "=", "01")], limit=1).id or False, # 01 = Anula documento de referencia
                "invoice_line_ids": [],
            }

            for line in return_lines:
                # Buscar la línea de la factura original para copiar impuestos y precios
                inv_line = invoice.invoice_line_ids.filtered(lambda il: il.product_id == line.product_id)[:1]
                
                line_vals = {
                    "product_id": line.product_id.id,
                    "quantity": line.quantity,
                    "product_uom_id": line.uom_id.id,
                    "price_unit": inv_line.price_unit if inv_line else line.product_id.list_price,
                    "tax_ids": [(6, 0, inv_line.tax_ids.ids)] if inv_line else [],
                    "discount": inv_line.discount if inv_line else 0.0,
                    "account_id": inv_line.account_id.id if inv_line else False,
                }
                move_vals["invoice_line_ids"].append((0, 0, line_vals))
            
            new_move = self.env["account.move"].create(move_vals)
            created_moves |= new_move

        if len(created_moves) == 1:
            return {
                "name": _("Nota de Crédito"),
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": created_moves.id,
                "view_mode": "form",
                "target": "current",
            }
        else:
            return {
                "name": _("Notas de Crédito Generadas"),
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "domain": [("id", "in", created_moves.ids)],
                "view_mode": "list,form",
                "target": "current",
            }

    def action_view_credit_notes(self):
        self.ensure_one()
        return {
            "name": _("Notas de Crédito"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "domain": [("id", "in", self.credit_note_ids.ids)],
            "view_mode": "list,form",
            "target": "current",
        }

    def unlink(self):
        for record in self:
            if record.state not in ("draft", "cancelled"):
                raise UserError(_("Solo puede eliminar devoluciones en borrador o canceladas."))
        return super().unlink()


class SngReturnLine(models.Model):
    _name = "sng.return.line"
    _description = "Linea de Devolucion"
    _order = "return_id, sequence, id"

    sequence = fields.Integer(default=10)
    return_id = fields.Many2one(
        "sng.return",
        string="Devolucion",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        related="return_id.partner_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        related="return_id.company_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        related="return_id.state",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        domain="[('sale_ok', '=', True)]",
    )
    quantity = fields.Float(
        string="Cantidad a devolver",
        required=True,
        default=1.0,
        digits="Product Unit of Measure",
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="UdM",
        related="product_id.uom_id",
        readonly=True,
    )
    notes = fields.Text(string="Notas")
    invoice_id = fields.Many2one(
        "account.move",
        string="Factura de origen",
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('partner_id', 'child_of', partner_id), ('invoice_line_ids.product_id', '=', product_id)]",
        help="Permite vincular este producto con una factura específica para generar la Nota de Crédito.",
    )
    invoiced_sale_qty = fields.Float(
        string="Vendido facturado",
        compute="_compute_sale_metrics",
        digits="Product Unit of Measure",
    )
    previous_return_qty = fields.Float(
        string="Devuelto antes",
        compute="_compute_sale_metrics",
        digits="Product Unit of Measure",
    )
    available_return_qty = fields.Float(
        string="Disponible",
        compute="_compute_sale_metrics",
        digits="Product Unit of Measure",
    )
    credit_note_qty = fields.Float(
        string="Nc emitidas",
        compute="_compute_sale_metrics",
        digits="Product Unit of Measure",
        help="Cantidad total reembolsada mediante notas de crédito (out_refund publicadas) para este producto y cliente.",
    )
    invoiced_sale_order_count = fields.Integer(
        string="Ordenes facturadas",
        compute="_compute_sale_metrics",
    )

    @api.depends("product_id", "partner_id", "company_id")
    def _compute_sale_metrics(self):
        sale_line_model = self.env["sale.order.line"]
        previous_return_model = self.env["sng.return.line"]
        move_line_model = self.env["account.move.line"]
        for line in self:
            if not line.product_id or not line.partner_id:
                line.invoiced_sale_qty = 0.0
                line.previous_return_qty = 0.0
                line.available_return_qty = 0.0
                line.credit_note_qty = 0.0
                line.invoiced_sale_order_count = 0
                continue

            commercial_partner = line.partner_id.commercial_partner_id
            sale_lines = sale_line_model.search([
                ("order_id.partner_id", "child_of", commercial_partner.id),
                ("order_id.state", "in", ["sale", "done"]),
                ("order_id.invoice_status", "=", "invoiced"),
                ("product_id", "=", line.product_id.id),
                ("company_id", "=", line.company_id.id),
                ("display_type", "=", False),
            ])
            previous_returns = previous_return_model.search([
                ("partner_id", "child_of", commercial_partner.id),
                ("product_id", "=", line.product_id.id),
                ("company_id", "=", line.company_id.id),
                ("state", "=", "confirmed"),
                ("id", "!=", line.id),
            ])
            # Notas de crédito (out_refund) publicadas para este producto y cliente
            credit_note_lines = move_line_model.search([
                ("move_id.move_type", "=", "out_refund"),
                ("move_id.state", "=", "posted"),
                ("move_id.partner_id", "child_of", commercial_partner.id),
                ("product_id", "=", line.product_id.id),
                ("company_id", "=", line.company_id.id),
                ("display_type", "not in", ("line_section", "line_note")),
            ])

            invoiced_qty = sum(sale_lines.mapped("product_uom_qty"))
            previous_qty = sum(previous_returns.mapped("quantity"))
            credit_qty = sum(credit_note_lines.mapped("quantity"))

            line.invoiced_sale_qty = invoiced_qty
            line.previous_return_qty = previous_qty
            line.credit_note_qty = credit_qty
            line.available_return_qty = max(0.0, invoiced_qty - previous_qty - credit_qty)
            line.invoiced_sale_order_count = len(sale_lines.mapped("order_id"))

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("La cantidad a devolver debe ser mayor a cero."))

    @api.constrains("quantity", "state", "product_id", "partner_id", "company_id")
    def _check_available_quantity(self):
        for line in self:
            if line.state == "confirmed":
                line._validate_return_quantity()

    @api.constrains("return_id", "product_id")
    def _check_unique_product_per_return(self):
        for line in self:
            if not line.return_id or not line.product_id:
                continue
            duplicated_lines = line.return_id.line_ids.filtered(lambda item: item.product_id == line.product_id)
            if len(duplicated_lines) > 1:
                raise ValidationError(
                    _("No puede repetir el mismo producto en una misma devolucion. Ajuste la cantidad en una sola linea.")
                )

    def _validate_return_quantity(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("Debe seleccionar un producto."))
        if self.quantity > self.available_return_qty:
            raise UserError(
                _(
                    "La cantidad a devolver de %(product)s (%(qty)s) excede lo disponible (%(available)s) "
                    "segun las ordenes facturadas del cliente."
                ) % {
                    "product": self.product_id.display_name,
                    "qty": self.quantity,
                    "available": self.available_return_qty,
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for line in records:
            if line.state and line.state != "draft":
                raise UserError(_("Solo puede agregar productos cuando la devolucion esta en borrador."))
        return records

    def write(self, vals):
        for line in self:
            if line.state and line.state != "draft":
                raise UserError(_("Solo puede modificar productos cuando la devolucion esta en borrador."))
        return super().write(vals)

    def unlink(self):
        for line in self:
            if line.state and line.state != "draft":
                raise UserError(_("Solo puede eliminar productos cuando la devolucion esta en borrador."))
        return super().unlink()

    def action_view_history(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Debe seleccionar un cliente antes de consultar el historial."))
        if not self.product_id:
            raise UserError(_("Debe seleccionar un producto antes de consultar el historial."))
        wizard_model = self.env["sng.return.history.wizard"]
        wizard = wizard_model.create({
            "partner_id": self.partner_id.id,
            "product_id": self.product_id.id,
            "company_id": self.company_id.id,
            "return_id": self.return_id.id,
            "return_line_id": self.id,
            "history_line_ids": wizard_model._build_history_commands(
                self.partner_id.id,
                self.product_id.id,
                self.company_id.id,
            ),
        })
        return {
            "name": _("Historial de ventas facturadas"),
            "type": "ir.actions.act_window",
            "res_model": "sng.return.history.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
