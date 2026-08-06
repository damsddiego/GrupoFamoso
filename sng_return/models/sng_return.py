import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare

# Campos de la sugerencia automatica de factura de origen (ver
# sng_return_suggestion.py). Se listan aqui porque write() necesita conocerlos
# para permitir escribirlos sobre lineas ya confirmadas.
SUGGESTION_FIELDS = {
    "suggested_invoice_id",
    "suggestion_score",
    "suggestion_confidence",
    "suggestion_reason",
    "suggestion_source",
    "suggestion_date",
}

# Campos que definen el documento de origen de la linea (factura del sistema o
# clave de una factura de un sistema anterior). Solo el Gerente de Devoluciones
# puede fijarlos y son los unicos editables tras confirmar la devolucion.
ORIGIN_INVOICE_FIELDS = {
    "invoice_id",
    "not_loaded_invoice",
    "not_loaded_invoice_date",
}


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
        if "company_id" in vals:
            target_company = self.env["res.company"].browse(vals["company_id"])
            for record in self:
                record.line_ids._validate_related_companies(target_company)
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

    def _prepare_credit_note_common_vals(self):
        self.ensure_one()
        move_vals = {
            "move_type": "out_refund",
            "partner_id": self.partner_id.id,
            "invoice_origin": self.name,
            "sng_return_id": self.id,
            "company_id": self.company_id.id,
            "tipo_documento": "NC",
            "invoice_line_ids": [],
        }
        account_move_fields = self.env["account.move"]._fields
        if "return_location_id" in account_move_fields:
            move_vals["return_location_id"] = self.location_dest_id.id
        if "stock_return_picking_id" in account_move_fields and self.picking_id:
            move_vals["stock_return_picking_id"] = self.picking_id.id
        return move_vals

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

        lines_without_invoice = self.line_ids.filtered(
            lambda l: not l.invoice_id and not l.not_loaded_invoice
        )
        if lines_without_invoice:
            raise UserError(_(
                "El Gerente de Devoluciones debe seleccionar la factura de origen "
                "(o indicar la factura original no cargada) de los siguientes "
                "productos antes de generar la nota de crédito: %(products)s."
            ) % {
                "products": ", ".join(
                    lines_without_invoice.mapped("product_id.display_name")
                ),
            })
        legacy_lines = self.line_ids.filtered(
            lambda l: not l.invoice_id and l.not_loaded_invoice
        )
        legacy_without_date = legacy_lines.filtered(
            lambda l: not l.not_loaded_invoice_date
        )
        if legacy_without_date:
            raise UserError(_(
                "Debe indicar la fecha de la factura original no cargada de los "
                "siguientes productos antes de generar la nota de crédito: %(products)s."
            ) % {
                "products": ", ".join(
                    legacy_without_date.mapped("product_id.display_name")
                ),
            })
        lines_with_invoice = self.line_ids.filtered(lambda l: l.invoice_id)
        if not lines_with_invoice and not legacy_lines:
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

            move_vals = self._prepare_credit_note_common_vals()
            move_vals.update({
                "reversed_entry_id": invoice.id,
                # Campos requeridos por cr_electronic_invoice para generar el XML a Hacienda
                "invoice_id": invoice.id,
                "reference_code_id": ref_code.id if ref_code else False,
                "reference_document_id": ref_document.id if ref_document else False,
                "economic_activity_id": invoice.economic_activity_id.id if invoice.economic_activity_id else False,
                "payment_methods_id": invoice.payment_methods_id.id if invoice.payment_methods_id else False,
            })

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

        # NC por factura original no cargada (venta de un sistema anterior):
        # una NC por clave. cr_electronic_invoice referencia el documento ante
        # Hacienda con not_loaded_invoice/not_loaded_invoice_date en lugar de
        # invoice_id. Sin factura en Odoo no hay precio ni impuestos de origen:
        # se usan la lista de precios y los impuestos de venta del producto, y
        # el gerente puede ajustarlos en la NC en borrador antes de validarla.
        legacy_groups = {}
        for line in legacy_lines:
            key = (line.not_loaded_invoice, line.not_loaded_invoice_date)
            legacy_groups.setdefault(key, self.env["sng.return.line"])
            legacy_groups[key] |= line
        for (clave, invoice_date), return_lines in legacy_groups.items():
            # Posiciones 30-31 de la clave: tipo de comprobante original
            # (01 FE, 02 ND, 03 NC, 04 TE); coincide con reference.document.
            ref_doc_code = clave[29:31]
            if ref_doc_code not in ("01", "02", "03", "04"):
                ref_doc_code = "01"
            ref_document = self.env["reference.document"].search(
                [("code", "=", ref_doc_code)], limit=1
            )

            move_vals = self._prepare_credit_note_common_vals()
            move_vals.update({
                "not_loaded_invoice": clave,
                "not_loaded_invoice_date": invoice_date,
                "reference_code_id": ref_code.id if ref_code else False,
                "reference_document_id": ref_document.id if ref_document else False,
            })
            for line in return_lines:
                product = line.product_id.with_company(self.company_id)
                taxes = product.taxes_id.filtered(
                    lambda tax: tax.company_id == self.company_id
                )
                move_vals["invoice_line_ids"].append((0, 0, {
                    "product_id": product.id,
                    "quantity": line.quantity,
                    "product_uom_id": line.uom_id.id,
                    "price_unit": product.list_price,
                    "tax_ids": [(6, 0, taxes.ids)],
                }))

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
    _check_company_auto = True

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
        check_company=True,
        domain="[('sale_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
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
        copy=False,
        check_company=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('partner_id', 'child_of', partner_id), ('invoice_line_ids.product_id', '=', product_id)]",
        help="Factura contra la que se devuelve el producto. El Gerente de "
             "Devoluciones puede asignarla o cambiarla en cualquier punto del "
             "proceso mientras no exista una nota de credito activa; es "
             "obligatoria antes de generar la nota de credito y, cuando esta "
             "asignada, determina la cantidad disponible a devolver.",
    )
    not_loaded_invoice = fields.Char(
        string="Factura original no cargada",
        size=50,
        copy=False,
        help="Clave numérica de 50 dígitos de la factura electrónica original "
             "cuando la venta se hizo en un sistema anterior y la factura no "
             "existe en Odoo. La nota de crédito la referenciará ante Hacienda "
             "como documento no cargado. Excluyente con la factura de origen.",
    )
    not_loaded_invoice_date = fields.Date(
        string="Fecha factura no cargada",
        copy=False,
        help="Fecha de emisión de la factura original no cargada. Se completa "
             "automáticamente desde la clave si es posible.",
    )
    invoice_editable = fields.Boolean(
        string="Puede editar factura",
        compute="_compute_invoice_editable",
    )
    invoiced_sale_qty = fields.Float(
        string="Facturado",
        compute="_compute_sale_metrics",
        compute_sudo=True,
        digits="Product Unit of Measure",
        help="Cantidad del producto en la factura de origen seleccionada; sin factura, "
             "cantidad facturada en las ordenes de venta del cliente.",
    )
    previous_return_qty = fields.Float(
        string="Devuelto antes",
        compute="_compute_sale_metrics",
        compute_sudo=True,
        digits="Product Unit of Measure",
        help="Cantidad ya devuelta (devoluciones confirmadas) contra la misma factura; "
             "sin factura, total devuelto por el cliente para este producto.",
    )
    available_return_qty = fields.Float(
        string="Disponible",
        compute="_compute_sale_metrics",
        compute_sudo=True,
        digits="Product Unit of Measure",
        help="Cantidad disponible a devolver. Con factura de origen seleccionada se "
             "calcula contra esa factura; sin factura, contra las ordenes facturadas "
             "del cliente.",
    )
    credit_note_qty = fields.Float(
        string="Nc emitidas",
        compute="_compute_sale_metrics",
        compute_sudo=True,
        digits="Product Unit of Measure",
        help="Cantidad reembolsada mediante notas de crédito externas: con factura "
             "seleccionada, las que reversan esa factura; sin factura, las NC manuales "
             "del cliente sin vinculo con ventas.",
    )
    invoiced_sale_order_count = fields.Integer(
        string="Ordenes facturadas",
        compute="_compute_sale_metrics",
        compute_sudo=True,
    )

    @api.depends("state", "return_id.credit_note_ids.state")
    def _compute_invoice_editable(self):
        # El Gerente de Devoluciones puede asignar o cambiar la factura de
        # origen en cualquier punto del proceso (borrador o confirmado),
        # mientras la devolucion no tenga una nota de credito activa.
        can_edit = self.env.su or self.env.user.has_group(
            "sng_return.group_sng_return_manager"
        )
        for line in self:
            line.invoice_editable = (
                can_edit
                and line.state in (False, "draft", "confirmed")
                and not line.return_id._get_active_credit_notes()
            )

    @api.depends("product_id", "partner_id", "company_id", "quantity", "state", "invoice_id")
    def _compute_sale_metrics(self):
        # Con factura de origen seleccionada el disponible se calcula contra esa
        # factura; sin factura se usa el calculo global por cliente (ordenes
        # facturadas), igual que antes de asignar la factura.
        invoice_lines = self.filtered(
            lambda l: l.product_id and l.invoice_id and l.invoice_id.state != "cancel"
        )
        partner_lines = (self - invoice_lines).filtered(
            lambda l: l.product_id and l.partner_id
        )
        for line in self - invoice_lines - partner_lines:
            line.invoiced_sale_qty = 0.0
            line.previous_return_qty = 0.0
            line.available_return_qty = 0.0
            line.credit_note_qty = 0.0
            line.invoiced_sale_order_count = 0
        if invoice_lines:
            invoice_lines._compute_sale_metrics_by_invoice()
        if partner_lines:
            partner_lines._compute_sale_metrics_by_partner()

    @api.model
    def _build_invoice_availability_maps(self, invoices, product_ids):
        """Mapas de disponibilidad indexados por (factura, producto).

        Devuelve un dict con cuatro mapas: ``invoiced`` (cantidad facturada),
        ``returned`` (devuelto en devoluciones confirmadas), ``credited``
        (cantidad de notas de credito externas al modulo) y ``orders``
        (conjunto de ordenes de venta que originaron la linea).

        Es la unica fuente de verdad del disponible: la usan tanto el calculo
        de metricas de la linea como el scoring de sugerencia de factura.
        """
        product_ids = list(product_ids)

        # Cantidad facturada por (factura, producto).
        invoiced_map = {}
        order_map = {}
        for invoice in invoices:
            for inv_line in invoice.invoice_line_ids:
                if inv_line.display_type != "product" or not inv_line.product_id:
                    continue
                key = (invoice.id, inv_line.product_id.id)
                qty = inv_line.quantity
                if inv_line.product_uom_id:
                    qty = inv_line.product_uom_id._compute_quantity(
                        qty, inv_line.product_id.uom_id
                    )
                invoiced_map[key] = invoiced_map.get(key, 0.0) + qty
                order_map.setdefault(key, set()).update(
                    inv_line.sale_line_ids.order_id.ids
                )

        # Devuelto antes: lineas confirmadas de este modulo sobre la misma factura.
        return_map = {
            (invoice.id, product.id): qty_sum or 0.0
            for invoice, product, qty_sum in self.env["sng.return.line"]._read_group(
                [
                    ("invoice_id", "in", invoices.ids),
                    ("product_id", "in", product_ids),
                    ("state", "=", "confirmed"),
                ],
                ["invoice_id", "product_id"],
                ["quantity:sum"],
            )
        }

        # NC externas que reversan la factura (las generadas por este modulo ya
        # cuentan en return_map via sus lineas de devolucion confirmadas).
        credit_map = {}
        refund_moves = self.env["account.move"].search([
            ("move_type", "=", "out_refund"),
            ("state", "=", "posted"),
            ("sng_return_id", "=", False),
            "|",
            ("reversed_entry_id", "in", invoices.ids),
            ("invoice_id", "in", invoices.ids),
        ])
        if refund_moves:
            for move, product, qty_sum in self.env["account.move.line"]._read_group(
                [
                    ("move_id", "in", refund_moves.ids),
                    ("product_id", "in", product_ids),
                    ("display_type", "=", "product"),
                ],
                ["move_id", "product_id"],
                ["quantity:sum"],
            ):
                origin = move.reversed_entry_id or move.invoice_id
                key = (origin.id, product.id)
                credit_map[key] = credit_map.get(key, 0.0) + (qty_sum or 0.0)

        return {
            "invoiced": invoiced_map,
            "returned": return_map,
            "credited": credit_map,
            "orders": order_map,
        }

    def _compute_sale_metrics_by_invoice(self):
        lines_with_data = self
        maps = self._build_invoice_availability_maps(
            lines_with_data.mapped("invoice_id"),
            {line.product_id.id for line in lines_with_data},
        )
        invoiced_map = maps["invoiced"]
        return_map = maps["returned"]
        credit_map = maps["credited"]
        order_map = maps["orders"]

        for line in lines_with_data:
            key = (line.invoice_id.id, line.product_id.id)
            invoiced_qty = invoiced_map.get(key, 0.0)
            previous_qty = return_map.get(key, 0.0)
            # Excluir la propia linea si ya esta confirmada (esta incluida
            # en el agregado); asi no se descuenta a si misma.
            if line.state == "confirmed" and isinstance(line.id, int):
                previous_qty = max(0.0, previous_qty - line.quantity)
            credit_qty = credit_map.get(key, 0.0)

            line.invoiced_sale_qty = invoiced_qty
            line.previous_return_qty = previous_qty
            line.credit_note_qty = credit_qty
            line.available_return_qty = max(0.0, invoiced_qty - previous_qty - credit_qty)
            line.invoiced_sale_order_count = len(order_map.get(key, ()))

    def _compute_sale_metrics_by_partner(self):
        # Agrupar por (cliente comercial, compania) para consultar en lote:
        # 3 read_group por grupo en lugar de 3 search por linea.
        groups = {}
        for line in self:
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

    @api.constrains("quantity", "state", "product_id", "partner_id", "company_id", "invoice_id")
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

    @api.onchange("not_loaded_invoice")
    def _onchange_not_loaded_invoice(self):
        clave = (self.not_loaded_invoice or "").strip()
        self.not_loaded_invoice = clave or False
        # La clave codifica la fecha de emision: posiciones 4-9 (ddmmaa),
        # tras el codigo de pais (506).
        if len(clave) == 50 and clave.isdigit() and not self.not_loaded_invoice_date:
            try:
                self.not_loaded_invoice_date = fields.Date.to_date(
                    "20%s-%s-%s" % (clave[7:9], clave[5:7], clave[3:5])
                )
            except ValueError:
                pass

    @api.onchange("invoice_id")
    def _onchange_invoice_id(self):
        # Factura del sistema y clave no cargada son excluyentes.
        if self.invoice_id:
            self.not_loaded_invoice = False
            self.not_loaded_invoice_date = False

    @api.constrains("not_loaded_invoice", "not_loaded_invoice_date", "invoice_id")
    def _check_not_loaded_invoice(self):
        for line in self:
            if not line.not_loaded_invoice:
                continue
            if line.invoice_id:
                raise ValidationError(_(
                    "La línea de %(product)s no puede tener a la vez una factura "
                    "de origen del sistema y una factura original no cargada."
                ) % {"product": line.product_id.display_name})
            if not re.fullmatch(r"\d{50}", line.not_loaded_invoice):
                raise ValidationError(_(
                    "La factura original no cargada de %(product)s debe ser la "
                    "clave numérica de exactamente 50 dígitos de la factura "
                    "electrónica original."
                ) % {"product": line.product_id.display_name})

    def _validate_related_companies(self, return_company=None):
        """Validate company-dependent values against the return header.

        ``company_id`` is a stored related field on the line. During nested
        One2many creation it may not be ready when Odoo runs its generic
        ``check_company`` validation, so compare against ``return_id``
        directly instead.
        """
        for line in self:
            company = return_company or line.return_id.company_id
            if not company:
                continue

            product = line.product_id.sudo()
            if product.company_id and product.company_id != company:
                raise ValidationError(_(
                    "El producto %(product)s pertenece a %(product_company)s y "
                    "no puede usarse en una devolución de %(return_company)s."
                ) % {
                    "product": product.display_name,
                    "product_company": product.company_id.display_name,
                    "return_company": company.display_name,
                })

            invoice = line.invoice_id.sudo()
            if invoice.company_id and invoice.company_id != company:
                raise ValidationError(_(
                    "La factura %(invoice)s pertenece a %(invoice_company)s y "
                    "no puede usarse en una devolución de %(return_company)s."
                ) % {
                    "invoice": invoice.display_name,
                    "invoice_company": invoice.company_id.display_name,
                    "return_company": company.display_name,
                })

    @api.constrains("return_id", "product_id", "invoice_id")
    def _check_related_companies(self):
        self._validate_related_companies()

    def _validate_return_quantity(self):
        self.ensure_one()
        if not self.product_id:
            raise ValidationError(_("Debe seleccionar un producto."))
        # Venta hecha en un sistema anterior: no existe trazabilidad en Odoo
        # contra la cual validar el disponible.
        if not self.invoice_id and self.not_loaded_invoice:
            return
        if self.quantity > self.available_return_qty:
            if self.invoice_id:
                source = _("segun la factura %(invoice)s") % {
                    "invoice": self.invoice_id.display_name,
                }
            else:
                source = _("segun las ordenes facturadas del cliente")
            raise ValidationError(
                _(
                    "La cantidad a devolver de %(product)s (%(qty)s) excede lo disponible "
                    "(%(available)s) %(source)s."
                ) % {
                    "product": self.product_id.display_name,
                    "qty": self.quantity,
                    "available": self.available_return_qty,
                    "source": source,
                }
            )

    def _check_invoice_manager_access(self):
        if self.env.su:
            return
        if not self.env.user.has_group("sng_return.group_sng_return_manager"):
            raise AccessError(_(
                "Solo el Gerente de Devoluciones puede seleccionar o modificar "
                "la factura de origen."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        if any(
            any(vals.get(field) for field in ORIGIN_INVOICE_FIELDS)
            for vals in vals_list
        ):
            self._check_invoice_manager_access()
        records = super().create(vals_list)
        for line in records:
            if line.state and line.state != "draft":
                raise UserError(_("Solo puede agregar productos cuando la devolucion esta en borrador."))
        return records

    def write(self, vals):
        if ORIGIN_INVOICE_FIELDS & set(vals):
            self._check_invoice_manager_access()
        for line in self:
            if line.state == "confirmed":
                # Sobre una linea confirmada solo se admite fijar la factura de
                # origen (del sistema o no cargada) y refrescar la sugerencia
                # automatica.
                if set(vals) - ORIGIN_INVOICE_FIELDS - SUGGESTION_FIELDS:
                    raise UserError(_(
                        "Después de confirmar la devolución solo puede modificar la factura "
                        "de origen."
                    ))
                if ORIGIN_INVOICE_FIELDS & set(vals) and line.return_id._get_active_credit_notes():
                    raise UserError(_(
                        "No puede modificar la factura de origen porque la devolución ya "
                        "tiene una nota de crédito activa."
                    ))
            elif line.state and line.state != "draft":
                raise UserError(_("Solo puede modificar productos cuando la devolucion esta en borrador."))
        # Cambiar producto o cantidad invalida la sugerencia calculada antes.
        if ("product_id" in vals or "quantity" in vals) and not (SUGGESTION_FIELDS & set(vals)):
            vals = dict(vals, **{
                "suggested_invoice_id": False,
                "suggestion_score": 0.0,
                "suggestion_confidence": False,
                "suggestion_reason": False,
                "suggestion_source": False,
                "suggestion_date": False,
            })
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
