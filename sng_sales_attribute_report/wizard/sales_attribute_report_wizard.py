# -*- coding: utf-8 -*-

import base64
import io
from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import file_path, format_amount, format_date

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:  # pragma: no cover - checked by the manifest too
    xlsxwriter = None


class SngSalesAttributeReportWizard(models.TransientModel):
    _name = "sng.sales.attribute.report.wizard"
    _description = "Asistente de facturación por atributos"

    date_from = fields.Date(
        string="Fecha inicial",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string="Fecha final",
        required=True,
        default=fields.Date.context_today,
    )
    company_ids = fields.Many2many(
        comodel_name="res.company",
        relation="sng_attr_report_wizard_company_rel",
        column1="wizard_id",
        column2="company_id",
        string="Compañías",
        required=True,
        default=lambda self: self.env.companies.ids,
    )
    attribute_ids = fields.Many2many(
        comodel_name="product.attribute",
        relation="sng_attr_report_wizard_attribute_rel",
        column1="wizard_id",
        column2="attribute_id",
        string="Atributos",
        required=True,
    )
    attribute_value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        relation="sng_attr_report_wizard_value_rel",
        column1="wizard_id",
        column2="value_id",
        string="Valores",
        required=True,
    )
    salesperson_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="sng_attr_report_wizard_salesperson_rel",
        column1="wizard_id",
        column2="partner_id",
        string="Vendedores",
        domain="[('is_salesperson', '=', True)]",
        help="Déjelo vacío para incluir todos los vendedores.",
    )
    show_results = fields.Boolean(default=False)
    excel_file = fields.Binary(string="Archivo Excel", readonly=True, attachment=False)
    excel_filename = fields.Char(string="Nombre del Excel", readonly=True)

    salesperson_line_ids = fields.One2many(
        "sng.sales.attribute.report.salesperson.line",
        "wizard_id",
        string="Por vendedor",
        readonly=True,
    )
    product_line_ids = fields.One2many(
        "sng.sales.attribute.report.product.line",
        "wizard_id",
        string="Por producto",
        readonly=True,
    )
    credit_note_line_ids = fields.One2many(
        "sng.sales.attribute.report.credit.note.line",
        "wizard_id",
        string="Notas de crédito",
        readonly=True,
    )
    excluded_line_ids = fields.One2many(
        "sng.sales.attribute.report.excluded.line",
        "wizard_id",
        string="Excluidos",
        readonly=True,
    )

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if not wizard.date_from or not wizard.date_to:
                continue
            if wizard.date_from > wizard.date_to:
                raise ValidationError(_("La fecha inicial no puede ser posterior a la final."))
            if wizard.date_to >= wizard.date_from + relativedelta(years=1):
                raise ValidationError(_("El rango máximo permitido es de un año."))

    @api.constrains("attribute_ids", "attribute_value_ids")
    def _check_attribute_values(self):
        for wizard in self:
            wizard._get_values_by_attribute()

    @api.onchange("attribute_ids")
    def _onchange_attribute_ids(self):
        self.attribute_value_ids = self.attribute_value_ids.filtered(
            lambda value: value.attribute_id in self.attribute_ids
        )
        self._clear_preview()

    @api.onchange(
        "date_from",
        "date_to",
        "company_ids",
        "attribute_value_ids",
        "salesperson_ids",
    )
    def _onchange_filters(self):
        self._clear_preview()

    def _clear_preview(self):
        self.show_results = False
        self.salesperson_line_ids = [Command.clear()]
        self.product_line_ids = [Command.clear()]
        self.credit_note_line_ids = [Command.clear()]
        self.excluded_line_ids = [Command.clear()]

    def _get_selected_companies(self):
        self.ensure_one()
        selected_ids = set(self.company_ids.ids)
        allowed_ids = set(self.env.user.company_ids.ids)
        context_company_ids = self.env.context.get("allowed_company_ids")
        if context_company_ids is not None:
            allowed_ids &= set(context_company_ids)
        if not selected_ids or not selected_ids.issubset(allowed_ids):
            raise UserError(_("Seleccione al menos una compañía permitida para su usuario."))
        return self.company_ids

    def _get_values_by_attribute(self):
        self.ensure_one()
        if not self.attribute_ids:
            raise ValidationError(_("Seleccione al menos un atributo."))
        if not self.attribute_value_ids:
            raise ValidationError(_("Seleccione al menos un valor de atributo."))

        unexpected = self.attribute_value_ids.filtered(
            lambda value: value.attribute_id not in self.attribute_ids
        )
        if unexpected:
            raise ValidationError(
                _("Hay valores seleccionados que no pertenecen a los atributos elegidos.")
            )

        result = {}
        for attribute in self.attribute_ids.sorted("id"):
            values = self.attribute_value_ids.filtered(
                lambda value, attribute=attribute: value.attribute_id == attribute
            )
            if not values:
                raise ValidationError(
                    _(
                        "Seleccione al menos un valor para el atributo %(attribute)s.",
                        attribute=attribute.display_name,
                    )
                )
            result[attribute] = values
        return result

    def _get_matching_products(self):
        """Resolve OR inside one attribute and AND between attributes."""
        self.ensure_one()
        values_by_attribute = self._get_values_by_attribute()
        product_ids = None

        for attribute, values in values_by_attribute.items():
            if attribute.create_variant == "no_variant":
                attribute_lines = self.env[
                    "product.template.attribute.line"
                ].with_context(active_test=False).search(
                    [
                        ("active", "=", True),
                        ("attribute_id", "=", attribute.id),
                        ("value_ids", "in", values.ids),
                    ]
                )
                matching_ids = set(
                    attribute_lines.product_tmpl_id.with_context(
                        active_test=False
                    ).product_variant_ids.ids
                )
            else:
                template_values = self.env[
                    "product.template.attribute.value"
                ].with_context(active_test=False).search(
                    [
                        ("ptav_active", "=", True),
                        ("attribute_id", "=", attribute.id),
                        ("product_attribute_value_id", "in", values.ids),
                    ]
                )
                matching_ids = set(
                    template_values.with_context(
                        active_test=False
                    ).ptav_product_variant_ids.ids
                )

            product_ids = matching_ids if product_ids is None else product_ids & matching_ids
            if not product_ids:
                break

        if not product_ids:
            raise UserError(_("No hay productos que cumplan la combinación de atributos."))
        return self.env["product.product"].with_context(active_test=False).browse(
            sorted(product_ids)
        )

    def _get_candidate_lines(self):
        self.ensure_one()
        companies = self._get_selected_companies()
        products = self._get_matching_products()
        domain = [
            ("company_id", "in", companies.ids),
            ("move_id.invoice_date", ">=", self.date_from),
            ("move_id.invoice_date", "<=", self.date_to),
            ("move_id.move_type", "in", ("out_invoice", "out_refund")),
            ("product_id", "in", products.ids),
        ]
        if self.salesperson_ids:
            domain.append(("move_id.salesperson_id", "in", self.salesperson_ids.ids))
        return self.env["account.move.line"].with_context(
            active_test=False,
            allowed_company_ids=companies.ids,
        ).search(domain, order="company_id, invoice_date, move_id, id")

    @staticmethod
    def _new_movement_row():
        return {
            "invoice_ids": set(),
            "credit_note_ids": set(),
            "move_ids": set(),
            "invoice_qty": 0.0,
            "credit_qty": 0.0,
            "invoice_subtotal": 0.0,
            "invoice_total": 0.0,
            "credit_subtotal": 0.0,
            "credit_total": 0.0,
        }

    @staticmethod
    def _finish_movement_row(row):
        row["invoice_count"] = len(row.pop("invoice_ids"))
        row["credit_note_count"] = len(row.pop("credit_note_ids"))
        row["move_ids"] = sorted(row["move_ids"])
        row["net_qty"] = row["invoice_qty"] - row["credit_qty"]
        row["net_subtotal"] = row["invoice_subtotal"] - row["credit_subtotal"]
        row["net_total"] = row["invoice_total"] - row["credit_total"]
        return row

    @staticmethod
    def _add_line_to_movement(row, move, quantity, subtotal, total):
        row["move_ids"].add(move.id)
        if move.move_type == "out_invoice":
            row["invoice_ids"].add(move.id)
            row["invoice_qty"] += quantity
            row["invoice_subtotal"] += subtotal
            row["invoice_total"] += total
        else:
            row["credit_note_ids"].add(move.id)
            row["credit_qty"] += quantity
            row["credit_subtotal"] += subtotal
            row["credit_total"] += total

    def _convert_to_company_currency(self, line, amount):
        move = line.move_id
        source_currency = move.currency_id
        target_currency = move.company_id.currency_id
        if source_currency == target_currency:
            return amount
        return source_currency._convert(
            amount,
            target_currency,
            move.company_id,
            move.invoice_date or move.date,
            round=True,
        )

    def _format_company_amounts(self, company, row, names):
        for name in names:
            row[f"{name}_display"] = format_amount(
                self.env, row.get(name, 0.0), company.currency_id
            )

    def _get_report_data(self):
        self.ensure_one()
        candidate_lines = self._get_candidate_lines()
        if not candidate_lines:
            raise UserError(_("No se encontraron líneas con los filtros seleccionados."))

        move_model = self.env["account.move"]
        move_type_labels = dict(
            move_model._fields["move_type"]._description_selection(self.env)
        )
        state_labels = dict(
            move_model._fields["state"]._description_selection(self.env)
        )
        hacienda_labels = dict(
            move_model._fields["state_tributacion"]._description_selection(self.env)
        )

        company_maps = {}

        def get_company_map(company):
            if company.id not in company_maps:
                company_maps[company.id] = {
                    "company_id": company.id,
                    "company_name": company.display_name,
                    "currency_id": company.currency_id.id,
                    "currency_name": company.currency_id.name,
                    "currency_symbol": company.currency_id.symbol or company.currency_id.name,
                    "totals": self._new_movement_row(),
                    "salesperson_map": {},
                    "product_map": {},
                    "price_map": {},
                    "note_map": {},
                    "excluded_map": {},
                    "details": [],
                }
            return company_maps[company.id]

        for line in candidate_lines:
            move = line.move_id
            company = move.company_id
            group = get_company_map(company)
            subtotal = self._convert_to_company_currency(line, line.price_subtotal)
            total = self._convert_to_company_currency(line, line.price_total)
            quantity = line.quantity
            accepted = move.state == "posted" and move.state_tributacion == "aceptado"

            if not accepted:
                hacienda_code = move.state_tributacion or "sin_estado"
                key = (move.move_type, move.state, hacienda_code)
                excluded = group["excluded_map"].setdefault(
                    key,
                    {
                        "company_id": company.id,
                        "currency_id": company.currency_id.id,
                        "move_type": move.move_type,
                        "move_type_name": move_type_labels.get(move.move_type, move.move_type),
                        "accounting_state": move.state,
                        "accounting_state_name": state_labels.get(move.state, move.state),
                        "hacienda_state": hacienda_code,
                        "hacienda_state_name": (
                            _("Sin estado")
                            if hacienda_code == "sin_estado"
                            else hacienda_labels.get(hacienda_code, hacienda_code)
                        ),
                        "move_ids": set(),
                        "subtotal": 0.0,
                        "total": 0.0,
                    },
                )
                excluded["move_ids"].add(move.id)
                excluded["subtotal"] += subtotal
                excluded["total"] += total
                continue

            self._add_line_to_movement(
                group["totals"], move, quantity, subtotal, total
            )

            salesperson = move.salesperson_id
            seller = group["salesperson_map"].setdefault(
                salesperson.id or False,
                {
                    **self._new_movement_row(),
                    "company_id": company.id,
                    "currency_id": company.currency_id.id,
                    "salesperson_id": salesperson.id or False,
                    "salesperson_name": salesperson.display_name or _("Sin vendedor"),
                },
            )
            self._add_line_to_movement(seller, move, quantity, subtotal, total)

            product = line.product_id
            product_row = group["product_map"].setdefault(
                product.id,
                {
                    **self._new_movement_row(),
                    "company_id": company.id,
                    "currency_id": company.currency_id.id,
                    "product_id": product.id,
                    "reference": product.default_code or product.product_tmpl_id.default_code or "",
                    "product_name": product.display_name,
                },
            )
            self._add_line_to_movement(product_row, move, quantity, subtotal, total)

            net_unit_price = line.price_subtotal / quantity if quantity else 0.0
            total_unit_price = line.price_total / quantity if quantity else 0.0
            price_key = (
                product.id,
                move.move_type,
                move.currency_id.id,
                round(line.price_unit, 6),
                round(line.discount, 6),
                round(net_unit_price, 6),
                round(total_unit_price, 6),
            )
            price_row = group["price_map"].setdefault(
                price_key,
                {
                    "company_id": company.id,
                    "product_id": product.id,
                    "reference": product.default_code or product.product_tmpl_id.default_code or "",
                    "product_name": product.display_name,
                    "move_type": move.move_type,
                    "move_type_name": move_type_labels.get(move.move_type, move.move_type),
                    "document_currency_id": move.currency_id.id,
                    "document_currency_name": move.currency_id.name,
                    "price_unit": line.price_unit,
                    "discount": line.discount,
                    "net_unit_price": net_unit_price,
                    "total_unit_price": total_unit_price,
                    "move_ids": set(),
                    "quantity": 0.0,
                    "subtotal": 0.0,
                    "total": 0.0,
                },
            )
            price_row["move_ids"].add(move.id)
            price_row["quantity"] += quantity
            price_row["subtotal"] += subtotal
            price_row["total"] += total

            group["details"].append(
                {
                    "move_id": move.id,
                    "invoice_date": fields.Date.to_string(move.invoice_date),
                    "move_type": move.move_type,
                    "move_type_name": move_type_labels.get(move.move_type, move.move_type),
                    "document": move.name or "",
                    "number_electronic": move.number_electronic or "",
                    "salesperson_name": salesperson.display_name or _("Sin vendedor"),
                    "customer_name": move.partner_id.display_name,
                    "product_id": product.id,
                    "reference": product.default_code or product.product_tmpl_id.default_code or "",
                    "product_name": product.display_name,
                    "document_currency_name": move.currency_id.name,
                    "quantity": quantity,
                    "price_unit": line.price_unit,
                    "discount": line.discount,
                    "net_unit_price": net_unit_price,
                    "total_unit_price": total_unit_price,
                    "source_subtotal": line.price_subtotal,
                    "source_total": line.price_total,
                    "company_subtotal": subtotal,
                    "company_total": total,
                }
            )

            if move.move_type == "out_refund":
                origin = move.invoice_id or move.reversed_entry_id
                note = group["note_map"].setdefault(
                    move.id,
                    {
                        "company_id": company.id,
                        "currency_id": company.currency_id.id,
                        "credit_note_id": move.id,
                        "credit_note_name": move.name or "",
                        "credit_note_date": fields.Date.to_string(move.invoice_date),
                        "salesperson_id": salesperson.id or False,
                        "salesperson_name": salesperson.display_name or _("Sin vendedor"),
                        "origin_move_id": origin.id or False,
                        "origin_name": origin.name or _("Sin enlace"),
                        "origin_date": (
                            fields.Date.to_string(origin.invoice_date)
                            if origin and origin.invoice_date
                            else ""
                        ),
                        "origin_hacienda": (
                            hacienda_labels.get(origin.state_tributacion, origin.state_tributacion)
                            if origin and origin.state_tributacion
                            else _("Sin estado")
                        ),
                        "subtotal": 0.0,
                        "total": 0.0,
                    },
                )
                note["subtotal"] += subtotal
                note["total"] += total

        groups = []
        movement_fields = (
            "invoice_subtotal",
            "invoice_total",
            "credit_subtotal",
            "credit_total",
            "net_subtotal",
            "net_total",
        )
        for company_id in sorted(company_maps):
            group = company_maps[company_id]
            company = self.env["res.company"].browse(company_id)
            group["totals"] = self._finish_movement_row(group["totals"])
            self._format_company_amounts(company, group["totals"], movement_fields)

            salespersons = []
            for row in group.pop("salesperson_map").values():
                self._finish_movement_row(row)
                self._format_company_amounts(company, row, movement_fields)
                salespersons.append(row)
            group["salespersons"] = sorted(
                salespersons,
                key=lambda row: (-row["net_total"], row["salesperson_name"].casefold()),
            )

            products = []
            for row in group.pop("product_map").values():
                self._finish_movement_row(row)
                row["average_invoice_price"] = (
                    row["invoice_subtotal"] / row["invoice_qty"]
                    if row["invoice_qty"]
                    else 0.0
                )
                self._format_company_amounts(
                    company, row, movement_fields + ("average_invoice_price",)
                )
                products.append(row)
            group["products"] = sorted(
                products,
                key=lambda row: (-row["net_total"], row["reference"], row["product_name"]),
            )

            prices = []
            for row in group.pop("price_map").values():
                row["document_count"] = len(row["move_ids"])
                row["move_ids"] = sorted(row["move_ids"])
                self._format_company_amounts(company, row, ("subtotal", "total"))
                prices.append(row)
            group["prices"] = sorted(
                prices,
                key=lambda row: (
                    row["reference"],
                    row["product_name"],
                    row["move_type"],
                    row["document_currency_name"],
                    row["price_unit"],
                    row["discount"],
                ),
            )

            notes = list(group.pop("note_map").values())
            for row in notes:
                self._format_company_amounts(company, row, ("subtotal", "total"))
            group["credit_notes"] = sorted(
                notes, key=lambda row: (row["credit_note_date"], row["credit_note_name"])
            )

            excluded = []
            for row in group.pop("excluded_map").values():
                row["document_count"] = len(row["move_ids"])
                row["move_ids"] = sorted(row["move_ids"])
                self._format_company_amounts(company, row, ("subtotal", "total"))
                excluded.append(row)
            group["excluded"] = sorted(
                excluded,
                key=lambda row: (
                    row["move_type_name"],
                    row["accounting_state_name"],
                    row["hacienda_state_name"],
                ),
            )
            group["details"].sort(
                key=lambda row: (row["invoice_date"], row["document"], row["product_name"])
            )
            groups.append(group)

        values_by_attribute = self._get_values_by_attribute()
        attribute_label = "; ".join(
            "%s: %s"
            % (
                attribute.display_name,
                ", ".join(values.mapped("name")),
            )
            for attribute, values in values_by_attribute.items()
        )
        companies = self._get_selected_companies()
        return {
            "date_from": fields.Date.to_string(self.date_from),
            "date_to": fields.Date.to_string(self.date_to),
            "date_from_display": format_date(self.env, self.date_from),
            "date_to_display": format_date(self.env, self.date_to),
            "company_names": ", ".join(companies.mapped("name")),
            "attribute_label": attribute_label,
            "salesperson_label": (
                ", ".join(self.salesperson_ids.mapped("display_name"))
                if self.salesperson_ids
                else _("Todos")
            ),
            "groups": groups,
        }

    def action_view_on_screen(self):
        self.ensure_one()
        data = self._get_report_data()
        seller_commands = [Command.clear()]
        product_commands = [Command.clear()]
        note_commands = [Command.clear()]
        excluded_commands = [Command.clear()]

        for group in data["groups"]:
            for row in group["salespersons"]:
                seller_commands.append(
                    Command.create(
                        {
                            "company_id": row["company_id"],
                            "currency_id": row["currency_id"],
                            "salesperson_id": row["salesperson_id"],
                            "salesperson_name": row["salesperson_name"],
                            "invoice_count": row["invoice_count"],
                            "invoice_qty": row["invoice_qty"],
                            "invoice_total": row["invoice_total"],
                            "credit_note_count": row["credit_note_count"],
                            "credit_qty": row["credit_qty"],
                            "credit_total": row["credit_total"],
                            "net_qty": row["net_qty"],
                            "net_total": row["net_total"],
                            "move_ids": [Command.set(row["move_ids"])],
                        }
                    )
                )
            for row in group["products"]:
                product_commands.append(
                    Command.create(
                        {
                            "company_id": row["company_id"],
                            "currency_id": row["currency_id"],
                            "product_id": row["product_id"],
                            "invoice_count": row["invoice_count"],
                            "invoice_qty": row["invoice_qty"],
                            "average_invoice_price": row["average_invoice_price"],
                            "invoice_total": row["invoice_total"],
                            "credit_note_count": row["credit_note_count"],
                            "credit_qty": row["credit_qty"],
                            "credit_total": row["credit_total"],
                            "net_qty": row["net_qty"],
                            "net_total": row["net_total"],
                            "move_ids": [Command.set(row["move_ids"])],
                        }
                    )
                )
            for row in group["credit_notes"]:
                note_commands.append(
                    Command.create(
                        {
                            "company_id": row["company_id"],
                            "currency_id": row["currency_id"],
                            "credit_note_id": row["credit_note_id"],
                            "salesperson_id": row["salesperson_id"],
                            "origin_move_id": row["origin_move_id"],
                            "subtotal": row["subtotal"],
                            "total": row["total"],
                        }
                    )
                )
            for row in group["excluded"]:
                excluded_commands.append(
                    Command.create(
                        {
                            "company_id": row["company_id"],
                            "currency_id": row["currency_id"],
                            "move_type": row["move_type"],
                            "accounting_state": row["accounting_state_name"],
                            "hacienda_state": row["hacienda_state_name"],
                            "document_count": row["document_count"],
                            "subtotal": row["subtotal"],
                            "total": row["total"],
                            "move_ids": [Command.set(row["move_ids"])],
                        }
                    )
                )

        self.write(
            {
                "salesperson_line_ids": seller_commands,
                "product_line_ids": product_commands,
                "credit_note_line_ids": note_commands,
                "excluded_line_ids": excluded_commands,
                "show_results": True,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Facturación por atributos"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref(
                "sng_sales_attribute_report.view_sales_attribute_report_wizard_form"
            ).id,
            "target": "current",
        }

    def action_print_pdf(self):
        self.ensure_one()
        data = self._get_report_data()
        return self.env.ref(
            "sng_sales_attribute_report.action_sales_attribute_report_pdf"
        ).report_action(self, data={"report_data": data})

    def _xlsx_formats(self, workbook):
        colors = {
            "ink": "#123E47",
            "teal": "#1BAAA0",
            "pink": "#F84E77",
            "pale_teal": "#E6F7F5",
            "pale_pink": "#FDE8EE",
            "border": "#D7E2E4",
        }

        def make(values):
            values.setdefault("font_name", "Space Grotesk")
            return workbook.add_format(values)

        return {
            "title": make(
                {
                    "bold": True,
                    "font_size": 18,
                    "font_color": "#FFFFFF",
                    "bg_color": colors["ink"],
                    "valign": "vcenter",
                }
            ),
            "subtitle": make({"font_size": 9, "font_color": "#56666A"}),
            "section": make(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": colors["teal"],
                    "border": 1,
                }
            ),
            "header": make(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": colors["ink"],
                    "border": 1,
                    "border_color": colors["border"],
                    "align": "center",
                    "valign": "vcenter",
                    "text_wrap": True,
                }
            ),
            "text": make({"border": 1, "border_color": colors["border"]}),
            "date": make(
                {
                    "border": 1,
                    "border_color": colors["border"],
                    "num_format": "dd/mm/yyyy",
                }
            ),
            "integer": make(
                {
                    "border": 1,
                    "border_color": colors["border"],
                    "num_format": "#,##0",
                    "align": "center",
                }
            ),
            "number": make(
                {
                    "border": 1,
                    "border_color": colors["border"],
                    "num_format": "#,##0.00",
                }
            ),
            "percent": make(
                {
                    "border": 1,
                    "border_color": colors["border"],
                    "num_format": '0.00"%"',
                }
            ),
            "money": make(
                {
                    "border": 1,
                    "border_color": colors["border"],
                    "num_format": "#,##0.00;[Red]-#,##0.00",
                }
            ),
            "total": make(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": colors["pink"],
                    "border": 1,
                    "num_format": "#,##0.00;[Red]-#,##0.00",
                }
            ),
            "total_text": make(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": colors["pink"],
                    "border": 1,
                }
            ),
            "kpi": make(
                {
                    "bold": True,
                    "font_size": 14,
                    "font_color": colors["pink"],
                    "bg_color": colors["pale_pink"],
                    "border": 1,
                    "align": "center",
                    "num_format": "#,##0.00",
                }
            ),
        }

    def _worksheet_title(self, worksheet, title, column_count, formats):
        worksheet.hide_gridlines(2)
        worksheet.set_row(0, 43)
        worksheet.merge_range(0, 0, 0, 1, "", formats["title"])
        worksheet.merge_range(0, 2, 0, column_count - 1, title, formats["title"])
        logo = file_path(
            "sng_sales_attribute_report/static/src/img/sngcloud-logo.png"
        )
        if logo:
            worksheet.insert_image(
                0,
                0,
                logo,
                {"x_scale": 0.72, "y_scale": 0.72, "x_offset": 5, "y_offset": 2},
            )

    def _generate_xlsx(self, data):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        workbook.set_properties(
            {
                "title": _("Facturación por atributos"),
                "author": "SNG Cloud",
                "company": data["company_names"],
            }
        )
        formats = self._xlsx_formats(workbook)

        summary = workbook.add_worksheet(_("Resumen")[:31])
        self._worksheet_title(summary, _("Facturación por atributos"), 10, formats)
        summary.set_column(0, 0, 36)
        summary.set_column(1, 9, 17)
        summary.merge_range(
            1,
            0,
            1,
            9,
            _(
                "Período: %(start)s al %(end)s | Atributos: %(attributes)s",
                start=data["date_from_display"],
                end=data["date_to_display"],
                attributes=data["attribute_label"],
            ),
            formats["subtitle"],
        )
        row_index = 3
        seller_headers = [
            _("Vendedor"),
            _("Facturas"),
            _("Cantidad facturada"),
            _("Subtotal facturado"),
            _("Total facturado"),
            _("Notas de crédito"),
            _("Cantidad NC"),
            _("Subtotal NC"),
            _("Total NC"),
            _("Total neto"),
        ]
        for group in data["groups"]:
            summary.merge_range(
                row_index,
                0,
                row_index,
                9,
                "%s (%s)" % (group["company_name"], group["currency_name"]),
                formats["section"],
            )
            row_index += 1
            for column, header in enumerate(seller_headers):
                summary.write(row_index, column, header, formats["header"])
            row_index += 1
            for line in group["salespersons"]:
                values = [
                    line["salesperson_name"],
                    line["invoice_count"],
                    line["invoice_qty"],
                    line["invoice_subtotal"],
                    line["invoice_total"],
                    line["credit_note_count"],
                    line["credit_qty"],
                    line["credit_subtotal"],
                    line["credit_total"],
                    line["net_total"],
                ]
                cell_formats = [
                    formats["text"],
                    formats["integer"],
                    formats["number"],
                    formats["money"],
                    formats["money"],
                    formats["integer"],
                    formats["number"],
                    formats["money"],
                    formats["money"],
                    formats["money"],
                ]
                for column, (value, cell_format) in enumerate(zip(values, cell_formats)):
                    summary.write(row_index, column, value, cell_format)
                row_index += 1
            totals = group["totals"]
            summary.write(row_index, 0, _("TOTAL"), formats["total_text"])
            for column, value in enumerate(
                [
                    totals["invoice_count"],
                    totals["invoice_qty"],
                    totals["invoice_subtotal"],
                    totals["invoice_total"],
                    totals["credit_note_count"],
                    totals["credit_qty"],
                    totals["credit_subtotal"],
                    totals["credit_total"],
                    totals["net_total"],
                ],
                start=1,
            ):
                summary.write(row_index, column, value, formats["total"])
            row_index += 2
        summary.freeze_panes(3, 1)

        product_sheet = workbook.add_worksheet(_("Resumen por producto")[:31])
        product_headers = [
            _("Compañía"), _("Moneda"), _("Referencia"), _("Producto"),
            _("Facturas"), _("Cantidad facturada"), _("Precio neto promedio"),
            _("Subtotal facturado"), _("Total facturado"), _("NC"),
            _("Cantidad NC"), _("Subtotal NC"), _("Total NC"),
            _("Cantidad neta"), _("Total neto"),
        ]
        self._worksheet_title(product_sheet, _("Productos que produjeron estos números"), len(product_headers), formats)
        product_sheet.set_column(0, 2, 18)
        product_sheet.set_column(3, 3, 55)
        product_sheet.set_column(4, 14, 18)
        for column, header in enumerate(product_headers):
            product_sheet.write(2, column, header, formats["header"])
        row_index = 3
        for group in data["groups"]:
            for line in group["products"]:
                values = [
                    group["company_name"], group["currency_name"], line["reference"],
                    line["product_name"], line["invoice_count"], line["invoice_qty"],
                    line["average_invoice_price"], line["invoice_subtotal"],
                    line["invoice_total"], line["credit_note_count"], line["credit_qty"],
                    line["credit_subtotal"], line["credit_total"], line["net_qty"],
                    line["net_total"],
                ]
                for column, value in enumerate(values):
                    cell_format = formats["text"] if column < 4 else (
                        formats["integer"] if column in (4, 9) else formats["money"]
                        if column in (6, 7, 8, 11, 12, 14) else formats["number"]
                    )
                    product_sheet.write(row_index, column, value, cell_format)
                row_index += 1
        product_sheet.autofilter(2, 0, max(row_index - 1, 2), len(product_headers) - 1)
        product_sheet.freeze_panes(3, 4)

        # Excel limits worksheet names to 31 characters.  This keeps the full
        # business meaning of "Auxiliar de precios y descuentos" within it.
        price_sheet = workbook.add_worksheet(_("Auxiliar precios y descuentos")[:31])
        price_headers = [
            _("Compañía"), _("Referencia"), _("Producto"), _("Movimiento"),
            _("Moneda precio"), _("Precio original"), _("Descuento %"),
            _("Precio neto"), _("Precio con impuesto"), _("Documentos"),
            _("Cantidad"), _("Subtotal compañía"), _("Total compañía"),
        ]
        self._worksheet_title(price_sheet, _("Precios que produjeron estos números"), len(price_headers), formats)
        price_sheet.set_column(0, 1, 18)
        price_sheet.set_column(2, 2, 55)
        price_sheet.set_column(3, 12, 18)
        for column, header in enumerate(price_headers):
            price_sheet.write(2, column, header, formats["header"])
        row_index = 3
        for group in data["groups"]:
            for line in group["prices"]:
                values = [
                    group["company_name"], line["reference"], line["product_name"],
                    line["move_type_name"], line["document_currency_name"], line["price_unit"],
                    line["discount"], line["net_unit_price"], line["total_unit_price"],
                    line["document_count"], line["quantity"], line["subtotal"], line["total"],
                ]
                for column, value in enumerate(values):
                    if column < 5:
                        cell_format = formats["text"]
                    elif column == 6:
                        cell_format = formats["percent"]
                    elif column == 9:
                        cell_format = formats["integer"]
                    elif column == 10:
                        cell_format = formats["number"]
                    else:
                        cell_format = formats["money"]
                    price_sheet.write(row_index, column, value, cell_format)
                row_index += 1
        price_sheet.autofilter(2, 0, max(row_index - 1, 2), len(price_headers) - 1)
        price_sheet.freeze_panes(3, 3)

        detail_sheet = workbook.add_worksheet(_("Detalle aceptado")[:31])
        detail_headers = [
            _("Compañía"), _("Fecha"), _("Tipo"), _("Documento"), _("Clave electrónica"),
            _("Vendedor"), _("Cliente"), _("Referencia"), _("Producto"),
            _("Moneda documento"), _("Cantidad"), _("Precio original"), _("Descuento %"),
            _("Precio neto"), _("Precio con impuesto"), _("Subtotal documento"),
            _("Total documento"), _("Subtotal compañía"), _("Total compañía"),
        ]
        self._worksheet_title(detail_sheet, _("Detalle aceptado por Hacienda"), len(detail_headers), formats)
        detail_sheet.set_column(0, 8, 20)
        detail_sheet.set_column(8, 8, 55)
        detail_sheet.set_column(9, 18, 18)
        for column, header in enumerate(detail_headers):
            detail_sheet.write(2, column, header, formats["header"])
        row_index = 3
        for group in data["groups"]:
            for line in group["details"]:
                values = [
                    group["company_name"], line["invoice_date"], line["move_type_name"],
                    line["document"], line["number_electronic"], line["salesperson_name"],
                    line["customer_name"], line["reference"], line["product_name"],
                    line["document_currency_name"], line["quantity"], line["price_unit"],
                    line["discount"], line["net_unit_price"], line["total_unit_price"],
                    line["source_subtotal"], line["source_total"], line["company_subtotal"],
                    line["company_total"],
                ]
                for column, value in enumerate(values):
                    if column < 10:
                        cell_format = formats["text"]
                    elif column == 10:
                        cell_format = formats["number"]
                    elif column == 12:
                        cell_format = formats["percent"]
                    else:
                        cell_format = formats["money"]
                    detail_sheet.write(row_index, column, value, cell_format)
                row_index += 1
        detail_sheet.autofilter(2, 0, max(row_index - 1, 2), len(detail_headers) - 1)
        detail_sheet.freeze_panes(3, 5)

        note_sheet = workbook.add_worksheet(_("Notas de crédito")[:31])
        note_headers = [
            _("Compañía"), _("Nota de crédito"), _("Fecha"), _("Vendedor"),
            _("Subtotal"), _("Total"), _("Factura origen"), _("Fecha origen"),
            _("Hacienda origen"),
        ]
        self._worksheet_title(note_sheet, _("Notas de crédito aceptadas"), len(note_headers), formats)
        note_sheet.set_column(0, 3, 27)
        note_sheet.set_column(4, 8, 20)
        for column, header in enumerate(note_headers):
            note_sheet.write(2, column, header, formats["header"])
        row_index = 3
        for group in data["groups"]:
            for line in group["credit_notes"]:
                values = [
                    group["company_name"], line["credit_note_name"], line["credit_note_date"],
                    line["salesperson_name"], line["subtotal"], line["total"],
                    line["origin_name"], line["origin_date"], line["origin_hacienda"],
                ]
                for column, value in enumerate(values):
                    note_sheet.write(
                        row_index,
                        column,
                        value,
                        formats["money"] if column in (4, 5) else formats["text"],
                    )
                row_index += 1
        note_sheet.autofilter(2, 0, max(row_index - 1, 2), len(note_headers) - 1)
        note_sheet.freeze_panes(3, 2)

        excluded_sheet = workbook.add_worksheet(_("Excluidos")[:31])
        excluded_headers = [
            _("Compañía"), _("Tipo"), _("Estado contable"), _("Estado Hacienda"),
            _("Documentos"), _("Subtotal"), _("Total"),
        ]
        self._worksheet_title(excluded_sheet, _("Documentos excluidos del total"), len(excluded_headers), formats)
        excluded_sheet.set_column(0, 3, 24)
        excluded_sheet.set_column(4, 6, 18)
        for column, header in enumerate(excluded_headers):
            excluded_sheet.write(2, column, header, formats["header"])
        row_index = 3
        for group in data["groups"]:
            for line in group["excluded"]:
                values = [
                    group["company_name"], line["move_type_name"],
                    line["accounting_state_name"], line["hacienda_state_name"],
                    line["document_count"], line["subtotal"], line["total"],
                ]
                for column, value in enumerate(values):
                    excluded_sheet.write(
                        row_index,
                        column,
                        value,
                        formats["integer"] if column == 4 else formats["money"]
                        if column in (5, 6) else formats["text"],
                    )
                row_index += 1
        excluded_sheet.autofilter(2, 0, max(row_index - 1, 2), len(excluded_headers) - 1)
        excluded_sheet.freeze_panes(3, 1)

        workbook.close()
        return output.getvalue()

    def action_print_excel(self):
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(_("La librería Python 'xlsxwriter' es necesaria."))
        data = self._get_report_data()
        content = self._generate_xlsx(data)
        filename = "facturacion_atributos_%s_%s.xlsx" % (
            data["date_from"],
            data["date_to"],
        )
        self.write(
            {
                "excel_file": base64.b64encode(content),
                "excel_filename": filename,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": (
                f"/web/content/{self._name}/{self.id}/excel_file/"
                f"{filename}?download=true"
            ),
            "target": "new",
        }

    def _open_moves(self, moves, title):
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
            "context": {
                "allowed_company_ids": self._get_selected_companies().ids,
            },
            "target": "current",
        }


class SngSalesAttributeReportSalespersonLine(models.TransientModel):
    _name = "sng.sales.attribute.report.salesperson.line"
    _description = "Facturación por atributos agrupada por vendedor"
    _order = "company_id, net_total desc, salesperson_name"

    wizard_id = fields.Many2one(
        "sng.sales.attribute.report.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    salesperson_id = fields.Many2one(
        "res.partner", string="Contacto vendedor", readonly=True
    )
    salesperson_name = fields.Char(string="Vendedor", readonly=True)
    invoice_count = fields.Integer(string="Facturas", readonly=True)
    invoice_qty = fields.Float(string="Cantidad facturada", readonly=True)
    invoice_total = fields.Monetary(string="Total facturado", readonly=True)
    credit_note_count = fields.Integer(string="Notas de crédito", readonly=True)
    credit_qty = fields.Float(string="Cantidad NC", readonly=True)
    credit_total = fields.Monetary(string="Total NC", readonly=True)
    net_qty = fields.Float(string="Cantidad neta", readonly=True)
    net_total = fields.Monetary(string="Total neto", readonly=True)
    move_ids = fields.Many2many(
        "account.move", "sng_attr_rpt_seller_move_rel", "line_id", "move_id"
    )

    def action_open_documents(self):
        self.ensure_one()
        return self.wizard_id._open_moves(
            self.move_ids, _("Documentos de %(seller)s", seller=self.salesperson_name)
        )


class SngSalesAttributeReportProductLine(models.TransientModel):
    _name = "sng.sales.attribute.report.product.line"
    _description = "Facturación por atributos agrupada por producto"
    _order = "company_id, net_total desc, product_id"

    wizard_id = fields.Many2one(
        "sng.sales.attribute.report.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    invoice_count = fields.Integer(string="Facturas", readonly=True)
    invoice_qty = fields.Float(string="Cantidad facturada", readonly=True)
    average_invoice_price = fields.Monetary(string="Precio neto promedio", readonly=True)
    invoice_total = fields.Monetary(string="Total facturado", readonly=True)
    credit_note_count = fields.Integer(string="Notas de crédito", readonly=True)
    credit_qty = fields.Float(string="Cantidad NC", readonly=True)
    credit_total = fields.Monetary(string="Total NC", readonly=True)
    net_qty = fields.Float(string="Cantidad neta", readonly=True)
    net_total = fields.Monetary(string="Total neto", readonly=True)
    move_ids = fields.Many2many(
        "account.move", "sng_attr_rpt_product_move_rel", "line_id", "move_id"
    )

    def action_open_documents(self):
        self.ensure_one()
        return self.wizard_id._open_moves(
            self.move_ids,
            _("Documentos de %(product)s", product=self.product_id.display_name),
        )


class SngSalesAttributeReportCreditNoteLine(models.TransientModel):
    _name = "sng.sales.attribute.report.credit.note.line"
    _description = "Nota de crédito del reporte por atributos"
    _order = "company_id, credit_note_id"

    wizard_id = fields.Many2one(
        "sng.sales.attribute.report.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    credit_note_id = fields.Many2one("account.move", string="Nota de crédito", readonly=True)
    salesperson_id = fields.Many2one("res.partner", string="Vendedor", readonly=True)
    origin_move_id = fields.Many2one("account.move", string="Factura origen", readonly=True)
    subtotal = fields.Monetary(string="Subtotal", readonly=True)
    total = fields.Monetary(string="Total", readonly=True)

    def action_open_credit_note(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.credit_note_id.display_name,
            "res_model": "account.move",
            "res_id": self.credit_note_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_origin(self):
        self.ensure_one()
        if not self.origin_move_id:
            raise UserError(_("La nota de crédito no tiene una factura origen enlazada."))
        return {
            "type": "ir.actions.act_window",
            "name": self.origin_move_id.display_name,
            "res_model": "account.move",
            "res_id": self.origin_move_id.id,
            "view_mode": "form",
            "target": "current",
        }


class SngSalesAttributeReportExcludedLine(models.TransientModel):
    _name = "sng.sales.attribute.report.excluded.line"
    _description = "Documentos excluidos del reporte por atributos"
    _order = "company_id, move_type, accounting_state, hacienda_state"

    wizard_id = fields.Many2one(
        "sng.sales.attribute.report.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    move_type = fields.Selection(
        [("out_invoice", "Factura"), ("out_refund", "Nota de crédito")],
        string="Tipo",
        readonly=True,
    )
    accounting_state = fields.Char(string="Estado contable", readonly=True)
    hacienda_state = fields.Char(string="Estado Hacienda", readonly=True)
    document_count = fields.Integer(string="Documentos", readonly=True)
    subtotal = fields.Monetary(string="Subtotal", readonly=True)
    total = fields.Monetary(string="Total", readonly=True)
    move_ids = fields.Many2many(
        "account.move", "sng_attr_rpt_excluded_move_rel", "line_id", "move_id"
    )

    def action_open_documents(self):
        self.ensure_one()
        return self.wizard_id._open_moves(
            self.move_ids, _("Documentos excluidos")
        )
