from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


class SngReturn(models.Model):
    _name = "sng.return"
    _description = "Devolucion de Cliente"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_request desc, id desc"

    name = fields.Char(
        string="Numero",
        required=True,
        copy=False,
        readonly=True,
        default="Nuevo",
    )
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        tracking=True,
        domain="[('customer_rank', '>', 0)]",
    )
    date_request = fields.Datetime(
        string="Fecha",
        required=True,
        tracking=True,
        default=fields.Datetime.now,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsable",
        required=True,
        tracking=True,
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
        tracking=True,
    )
    reason_id = fields.Many2one(
        "sng.return.reason",
        string="Motivo",
        required=True,
        tracking=True,
    )
    notes = fields.Text(string="Notas")
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Almacén de devolución",
        check_company=True,
        tracking=True,
        copy=False,
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        string="Ubicación destino",
        check_company=True,
        tracking=True,
        copy=False,
    )
    picking_id = fields.Many2one(
        "stock.picking",
        string="Recepción principal",
        check_company=True,
        readonly=True,
        copy=False,
    )
    picking_ids = fields.One2many(
        "stock.picking",
        "sng_return_id",
        string="Recepciones",
    )
    picking_count = fields.Integer(
        string="Cantidad de recepciones",
        compute="_compute_receipt_status",
    )
    receipt_complete = fields.Boolean(
        string="Recepción completa",
        compute="_compute_receipt_status",
    )
    receipt_state = fields.Selection(
        [
            ("not_required", "No requerida"),
            ("missing", "Sin recepción"),
            ("pending", "Pendiente"),
            ("done", "Recibido"),
        ],
        string="Estado de recepción",
        compute="_compute_receipt_status",
    )
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
    credit_note_ids = fields.One2many(
        "account.move",
        "sng_return_id",
        string="Notas de Crédito",
    )
    credit_note_count = fields.Integer(
        string="Cant. NC",
        compute="_compute_credit_note_count",
    )
    active_credit_note_count = fields.Integer(
        string="Cant. NC activas",
        compute="_compute_credit_note_count",
    )

    @api.depends("credit_note_ids", "credit_note_ids.state")
    def _compute_credit_note_count(self):
        for record in self:
            record.credit_note_count = len(record.credit_note_ids)
            record.active_credit_note_count = len(record._get_active_credit_notes())

    @api.depends(
        "line_ids.quantity",
        "line_ids.uom_id",
        "line_ids.product_id.is_storable",
        "picking_ids.state",
        "picking_ids.move_ids.state",
        "picking_ids.move_ids.quantity",
        "picking_ids.move_ids.product_id",
        "picking_ids.move_ids.product_uom",
    )
    def _compute_receipt_status(self):
        for record in self:
            record.picking_count = len(record.picking_ids)
            stock_lines = record._get_stock_return_lines()
            if not stock_lines:
                record.receipt_complete = True
                record.receipt_state = "not_required"
                continue

            done_moves = record.picking_ids.mapped("move_ids").filtered(
                lambda move: move.state == "done"
            )
            complete = True
            for line in stock_lines:
                product_moves = done_moves.filtered(
                    lambda move: move.product_id == line.product_id
                )
                received_qty = sum(
                    move.product_uom._compute_quantity(move.quantity, line.uom_id)
                    for move in product_moves
                )
                if float_compare(
                    received_qty,
                    line.quantity,
                    precision_rounding=line.uom_id.rounding,
                ) < 0:
                    complete = False
                    break

            record.receipt_complete = complete
            if complete:
                record.receipt_state = "done"
            elif record.picking_ids.filtered(lambda picking: picking.state != "cancel"):
                record.receipt_state = "pending"
            else:
                record.receipt_state = "missing"

    @api.depends("line_ids.quantity")
    def _compute_totals(self):
        for record in self:
            record.line_count = len(record.line_ids)
            record.total_qty = sum(record.line_ids.mapped("quantity"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Se compara contra el literal sin traducir para no depender del
            # idioma del usuario que crea el registro.
            if vals.get("name", "Nuevo") in (False, "Nuevo", _("Nuevo")):
                company_id = vals.get("company_id", self.env.company.id)
                seq = self.env["ir.sequence"].with_company(company_id).next_by_code("sng.return")
                vals["name"] = seq or "Nuevo"
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

    def _get_active_credit_notes(self):
        return self.credit_note_ids.filtered(lambda move: move.state != "cancel")

    def _get_stock_return_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(lambda line: line.product_id.is_storable)

    def _validate_before_confirmation(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Debe agregar al menos un producto a devolver."))
        for line in self.line_ids:
            line._validate_return_quantity()

    def _get_default_return_warehouse(self):
        self.ensure_one()
        sale_warehouses = self.line_ids.invoice_id.invoice_line_ids.sale_line_ids.order_id.mapped(
            "warehouse_id"
        ).filtered(lambda warehouse: warehouse.company_id == self.company_id)
        if len(sale_warehouses) == 1:
            return sale_warehouses

        user_warehouse = self.env.user.with_company(self.company_id)._get_default_warehouse_id()
        if user_warehouse and user_warehouse.company_id == self.company_id:
            return user_warehouse
        return self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_id.id)],
            limit=1,
        )

    @api.model
    def _get_return_destination_location(self, warehouse):
        if not warehouse:
            return self.env["stock.location"]
        return warehouse.in_type_id.default_location_dest_id or warehouse.lot_stock_id

    def _open_confirm_wizard(self):
        self.ensure_one()
        wizard = self.env["sng.return.confirm.wizard"].create({
            "return_id": self.id,
            "warehouse_id": self._get_default_return_warehouse().id,
        })
        return {
            "name": _("Seleccionar almacén de devolución"),
            "type": "ir.actions.act_window",
            "res_model": "sng.return.confirm.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm(self):
        self.ensure_one()
        self._check_supervisor_access()
        if self.state != "draft":
            raise UserError(_("Solo puede confirmar una devolución en estado borrador."))
        self._validate_before_confirmation()
        return self._open_confirm_wizard()

    def action_prepare_receipt(self):
        self.ensure_one()
        self._check_supervisor_access()
        if self.state != "confirmed":
            raise UserError(_("La devolución debe estar confirmada para preparar la recepción."))
        if self.picking_ids.filtered(lambda picking: picking.state != "cancel"):
            raise UserError(_("Esta devolución ya tiene una recepción activa."))
        self._validate_before_confirmation()
        return self._open_confirm_wizard()

    def _prepare_return_picking_vals(self, warehouse, location_dest):
        self.ensure_one()
        picking_type = warehouse.in_type_id
        if not picking_type:
            raise UserError(_(
                "El almacén %(warehouse)s no tiene configurado un tipo de operación de recepción."
            ) % {"warehouse": warehouse.display_name})

        location_src = (
            self.partner_id.with_company(self.company_id).property_stock_customer
            or self.env.ref("stock.stock_location_customers")
        )
        if not location_src:
            raise UserError(_("No se encontró la ubicación de clientes para crear la recepción."))

        move_commands = []
        for line in self._get_stock_return_lines():
            move_commands.append((0, 0, {
                "name": _("Devolución: %s") % line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity,
                "product_uom": line.uom_id.id,
                "location_id": location_src.id,
                "location_dest_id": location_dest.id,
                "picking_type_id": picking_type.id,
            }))

        return {
            "picking_type_id": picking_type.id,
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "origin": self.name,
            "location_id": location_src.id,
            "location_dest_id": location_dest.id,
            "sng_return_id": self.id,
            "move_ids": move_commands,
        }

    def _confirm_with_warehouse(self, warehouse):
        self.ensure_one()
        self._check_supervisor_access()
        if self.state not in ("draft", "confirmed"):
            raise UserError(_("No puede preparar una recepción para una devolución cancelada."))
        if warehouse.company_id != self.company_id:
            raise UserError(_("El almacén seleccionado pertenece a otra compañía."))
        if self.picking_ids.filtered(lambda picking: picking.state != "cancel"):
            raise UserError(_("Esta devolución ya tiene una recepción activa."))

        self._validate_before_confirmation()
        location_dest = self._get_return_destination_location(warehouse)
        if not location_dest or location_dest.usage != "internal":
            raise UserError(_(
                "El almacén %(warehouse)s no tiene una ubicación interna de recepción válida."
            ) % {"warehouse": warehouse.display_name})

        picking = self.env["stock.picking"]
        if self._get_stock_return_lines():
            picking = self.env["stock.picking"].with_company(self.company_id).create(
                self._prepare_return_picking_vals(warehouse, location_dest)
            )
            picking.action_confirm()

        vals = {
            "warehouse_id": warehouse.id,
            "location_dest_id": location_dest.id,
            "picking_id": picking.id,
        }
        if self.state == "draft":
            vals["state"] = "confirmed"
        self.write(vals)
        return picking

    def action_cancel(self):
        self._check_supervisor_access()
        for record in self:
            if record._get_active_credit_notes():
                raise UserError(_(
                    "No puede cancelar la devolucion %(name)s porque tiene notas de credito "
                    "asociadas. Cancele primero las notas de credito."
                ) % {"name": record.name})
            active_pickings = record.picking_ids.filtered(
                lambda picking: picking.state != "cancel"
            )
            if active_pickings.filtered(lambda picking: picking.state == "done"):
                raise UserError(_(
                    "No puede cancelar la devolución %(name)s porque tiene recepciones validadas."
                ) % {"name": record.name})
            active_pickings.action_cancel()
            record.state = "cancelled"

    def action_set_to_draft(self):
        self._check_supervisor_access()
        self.write({
            "state": "draft",
            "warehouse_id": False,
            "location_dest_id": False,
            "picking_id": False,
        })

    def action_view_pickings(self):
        self.ensure_one()
        pickings = self.picking_ids
        if not pickings:
            raise UserError(_("Esta devolución no tiene recepciones asociadas."))
        action = {
            "name": _("Recepciones de devolución"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", pickings.ids)],
            "context": {"create": False},
        }
        if len(pickings) == 1:
            action.update({"view_mode": "form", "res_id": pickings.id})
        return action

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

    # Mapeo de tipo_documento de la factura original al código de reference.document
    _TIPO_DOC_TO_REF_DOC_CODE = {
        "FE": "01",   # Factura Electrónica
        "FEE": "01",  # Factura Electrónica de Exportación
        "TE": "04",   # Tiquete Electrónico
        "ND": "02",   # Nota de Débito
        "NC": "03",   # Nota de Crédito
    }

    def action_generate_credit_note(self):
        self.ensure_one()
        if self.state != "confirmed":
            raise UserError(_("La devolución debe estar confirmada para generar la nota de crédito."))
        # El botón se oculta en la vista, pero se revalida aquí para evitar
        # duplicados por doble clic o llamadas RPC directas.
        if self._get_active_credit_notes():
            raise UserError(_(
                "Esta devolución ya tiene notas de crédito generadas. "
                "Cancélelas antes de generar nuevas."
            ))
        if not self.receipt_complete:
            raise UserError(_(
                "Debe recibir completamente los productos en el almacén antes de generar "
                "la nota de crédito."
            ))

        lines_with_invoice = self.line_ids.filtered(lambda l: l.invoice_id)
        if not lines_with_invoice:
            raise UserError(_("Ninguna línea tiene una factura asociada para generar la nota de crédito."))

        invoices = lines_with_invoice.mapped("invoice_id")
        created_moves = self.env["account.move"]

        # Código 06 = Devolución de mercancía (correcto para devoluciones)
        ref_code = self.env["reference.code"].search([("code", "=", "06")], limit=1)

        for invoice in invoices:
            return_lines = lines_with_invoice.filtered(lambda l: l.invoice_id == invoice)

            # Derivar reference_document desde tipo_documento de la factura original
            inv_tipo = invoice.tipo_documento or "FE"
            ref_doc_code = self._TIPO_DOC_TO_REF_DOC_CODE.get(inv_tipo, "01")
            ref_document = self.env["reference.document"].search(
                [("code", "=", ref_doc_code)], limit=1
            )

            move_vals = {
                "move_type": "out_refund",
                "partner_id": self.partner_id.id,
                "invoice_origin": self.name,
                "sng_return_id": self.id,
                "company_id": self.company_id.id,
                "reversed_entry_id": invoice.id,
                "tipo_documento": "NC",
                # Campos requeridos por cr_electronic_invoice para generar el XML a Hacienda
                "invoice_id": invoice.id,
                "reference_code_id": ref_code.id if ref_code else False,
                "reference_document_id": ref_document.id if ref_document else False,
                "economic_activity_id": invoice.economic_activity_id.id if invoice.economic_activity_id else False,
                "payment_methods_id": invoice.payment_methods_id.id if invoice.payment_methods_id else False,
                "invoice_line_ids": [],
            }
            account_move_fields = self.env["account.move"]._fields
            if "return_location_id" in account_move_fields:
                move_vals["return_location_id"] = self.location_dest_id.id
            if "stock_return_picking_id" in account_move_fields and self.picking_id:
                move_vals["stock_return_picking_id"] = self.picking_id.id

            for line in return_lines:
                inv_lines = invoice.invoice_line_ids.filtered(
                    lambda il: il.product_id == line.product_id
                    and il.display_type not in ("line_section", "line_note")
                )
                invoiced_qty = sum(inv_lines.mapped("quantity"))
                if inv_lines and line.quantity > invoiced_qty:
                    raise UserError(_(
                        "La cantidad a devolver de %(product)s (%(qty)s) excede la cantidad "
                        "facturada (%(invoiced)s) en la factura %(invoice)s."
                    ) % {
                        "product": line.product_id.display_name,
                        "qty": line.quantity,
                        "invoiced": invoiced_qty,
                        "invoice": invoice.name,
                    })
                # Si el producto aparece en varias lineas de la factura, se toma
                # la de mayor cantidad de forma deterministica.
                inv_line = inv_lines.sorted(lambda il: (il.quantity, il.id), reverse=True)[:1]
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
        compute_sudo=True,
        digits="Product Unit of Measure",
    )
    previous_return_qty = fields.Float(
        string="Devuelto antes",
        compute="_compute_sale_metrics",
        compute_sudo=True,
        digits="Product Unit of Measure",
    )
    available_return_qty = fields.Float(
        string="Disponible",
        compute="_compute_sale_metrics",
        compute_sudo=True,
        digits="Product Unit of Measure",
    )
    credit_note_qty = fields.Float(
        string="Nc emitidas",
        compute="_compute_sale_metrics",
        compute_sudo=True,
        digits="Product Unit of Measure",
        help="Cantidad reembolsada mediante notas de crédito manuales (sin devolución "
             "asociada ni vínculo con ventas) para este producto y cliente.",
    )
    invoiced_sale_order_count = fields.Integer(
        string="Ordenes facturadas",
        compute="_compute_sale_metrics",
        compute_sudo=True,
    )

    @api.depends("product_id", "partner_id", "company_id", "quantity", "state")
    def _compute_sale_metrics(self):
        lines_with_data = self.filtered(lambda l: l.product_id and l.partner_id)
        for line in self - lines_with_data:
            line.invoiced_sale_qty = 0.0
            line.previous_return_qty = 0.0
            line.available_return_qty = 0.0
            line.credit_note_qty = 0.0
            line.invoiced_sale_order_count = 0

        # Agrupar por (cliente comercial, compania) para consultar en lote:
        # 3 read_group por grupo en lugar de 3 search por linea.
        groups = {}
        for line in lines_with_data:
            key = (line.partner_id.commercial_partner_id.id, line.company_id.id)
            groups.setdefault(key, []).append(line)

        for (partner_id, company_id), group_lines in groups.items():
            product_ids = list({line.product_id.id for line in group_lines})

            # Cantidad facturada real (qty_invoiced ya descuenta las NC
            # vinculadas a lineas de venta, p.ej. reversiones estandar).
            sale_map = {
                product.id: (qty_sum or 0.0, order_count)
                for product, qty_sum, order_count in self.env["sale.order.line"]._read_group(
                    [
                        ("order_id.partner_id", "child_of", partner_id),
                        ("order_id.state", "in", ["sale", "done"]),
                        ("product_id", "in", product_ids),
                        ("company_id", "=", company_id),
                        ("display_type", "=", False),
                        ("qty_invoiced", ">", 0),
                    ],
                    ["product_id"],
                    ["qty_invoiced:sum", "order_id:count_distinct"],
                )
            }
            return_map = {
                product.id: qty_sum or 0.0
                for product, qty_sum in self.env["sng.return.line"]._read_group(
                    [
                        ("partner_id", "child_of", partner_id),
                        ("product_id", "in", product_ids),
                        ("company_id", "=", company_id),
                        ("state", "=", "confirmed"),
                    ],
                    ["product_id"],
                    ["quantity:sum"],
                )
            }
            # Solo NC "externas": sin devolucion asociada (las de este modulo ya
            # cuentan en return_map) y sin vinculo a lineas de venta (esas ya
            # netean qty_invoiced). Evita el doble descuento.
            credit_map = {
                product.id: qty_sum or 0.0
                for product, qty_sum in self.env["account.move.line"]._read_group(
                    [
                        ("move_id.move_type", "=", "out_refund"),
                        ("move_id.state", "=", "posted"),
                        ("move_id.partner_id", "child_of", partner_id),
                        ("move_id.sng_return_id", "=", False),
                        ("sale_line_ids", "=", False),
                        ("product_id", "in", product_ids),
                        ("company_id", "=", company_id),
                        ("display_type", "=", "product"),
                    ],
                    ["product_id"],
                    ["quantity:sum"],
                )
            }

            for line in group_lines:
                product_id = line.product_id.id
                invoiced_qty, order_count = sale_map.get(product_id, (0.0, 0))
                previous_qty = return_map.get(product_id, 0.0)
                # Excluir la propia linea si ya esta confirmada (esta incluida
                # en el agregado); asi no se descuenta a si misma.
                if line.state == "confirmed" and isinstance(line.id, int):
                    previous_qty = max(0.0, previous_qty - line.quantity)
                credit_qty = credit_map.get(product_id, 0.0)

                line.invoiced_sale_qty = invoiced_qty
                line.previous_return_qty = previous_qty
                line.credit_note_qty = credit_qty
                line.available_return_qty = max(0.0, invoiced_qty - previous_qty - credit_qty)
                line.invoiced_sale_order_count = order_count

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
            raise ValidationError(_("Debe seleccionar un producto."))
        if self.quantity > self.available_return_qty:
            raise ValidationError(
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
            if line.state == "confirmed":
                if set(vals) - {"invoice_id"}:
                    raise UserError(_(
                        "Después de confirmar la devolución solo puede modificar la factura "
                        "de origen."
                    ))
                if line.return_id._get_active_credit_notes():
                    raise UserError(_(
                        "No puede modificar la factura de origen porque la devolución ya "
                        "tiene una nota de crédito activa."
                    ))
            elif line.state and line.state != "draft":
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
