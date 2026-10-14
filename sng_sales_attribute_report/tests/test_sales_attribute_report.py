# -*- coding: utf-8 -*-

import io
import os
import zipfile

from PyPDF2 import PdfReader

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import file_path
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestSalesAttributeReport(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.payment_method = cls.env.ref(
            "cr_electronic_invoice.PaymentMethods_1"
        )
        cls.env.company.payment_method_default_id = cls.payment_method
        cls.salesperson = cls.env["res.partner"].create(
            {"name": "Vendedor Armor", "is_salesperson": True}
        )

        cls.brand_attribute = cls.env["product.attribute"].create(
            {"name": "Marca reporte", "create_variant": "always"}
        )
        cls.armor_value, cls.other_brand_value = cls.env[
            "product.attribute.value"
        ].create(
            [
                {"name": "Armor", "attribute_id": cls.brand_attribute.id},
                {"name": "Otra", "attribute_id": cls.brand_attribute.id},
            ]
        )
        cls.color_attribute = cls.env["product.attribute"].create(
            {"name": "Color reporte", "create_variant": "always"}
        )
        cls.black_value, cls.red_value = cls.env["product.attribute.value"].create(
            [
                {"name": "Negro", "attribute_id": cls.color_attribute.id},
                {"name": "Rojo", "attribute_id": cls.color_attribute.id},
            ]
        )
        cls.catalog_attribute = cls.env["product.attribute"].create(
            {"name": "Catálogo reporte", "create_variant": "no_variant"}
        )
        cls.promo_value = cls.env["product.attribute.value"].create(
            {"name": "Promoción", "attribute_id": cls.catalog_attribute.id}
        )

        cls.armor_template = cls.env["product.template"].create(
            {
                "name": "Producto Armor",
                "taxes_id": [Command.clear()],
                "supplier_taxes_id": [Command.clear()],
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": cls.brand_attribute.id,
                            "value_ids": [Command.set(cls.armor_value.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "attribute_id": cls.color_attribute.id,
                            "value_ids": [Command.set((cls.black_value | cls.red_value).ids)],
                        }
                    ),
                    Command.create(
                        {
                            "attribute_id": cls.catalog_attribute.id,
                            "value_ids": [Command.set(cls.promo_value.ids)],
                        }
                    ),
                ],
            }
        )
        cls.armor_black = cls._variant_with_value(cls.armor_template, cls.black_value)
        cls.armor_red = cls._variant_with_value(cls.armor_template, cls.red_value)
        cls.armor_black.default_code = "ARM-BLK"
        cls.armor_red.default_code = "ARM-RED"

        cls.other_template = cls.env["product.template"].create(
            {
                "name": "Producto de otra marca",
                "taxes_id": [Command.clear()],
                "supplier_taxes_id": [Command.clear()],
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": cls.brand_attribute.id,
                            "value_ids": [Command.set(cls.other_brand_value.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "attribute_id": cls.color_attribute.id,
                            "value_ids": [Command.set(cls.black_value.ids)],
                        }
                    ),
                ],
            }
        )
        cls.other_black = cls.other_template.product_variant_id
        cls.other_black.default_code = "OTHER-BLK"

        cls.origin_invoice = cls._make_move(
            "out_invoice",
            fields.Date.from_string("2026-08-31"),
            [(cls.armor_black, 1.0, 20.0, 0.0)],
            state="posted",
            hacienda="aceptado",
            salesperson=cls.salesperson,
        )
        cls.accepted_invoice = cls._make_move(
            "out_invoice",
            fields.Date.from_string("2026-09-15"),
            [
                (cls.armor_black, 2.0, 100.0, 10.0),
                (cls.armor_red, 1.0, 50.0, 0.0),
                (cls.other_black, 1.0, 30.0, 0.0),
            ],
            state="posted",
            hacienda="aceptado",
            salesperson=cls.salesperson,
        )
        cls.no_salesperson_invoice = cls._make_move(
            "out_invoice",
            fields.Date.from_string("2026-09-16"),
            [(cls.armor_black, 1.0, 10.0, 0.0)],
            state="posted",
            hacienda="aceptado",
            salesperson=False,
        )
        cls.linked_refund = cls._make_move(
            "out_refund",
            fields.Date.from_string("2026-09-20"),
            [(cls.armor_black, 1.0, 20.0, 0.0)],
            state="posted",
            hacienda="aceptado",
            salesperson=cls.salesperson,
            origin=cls.origin_invoice,
        )
        cls.unlinked_refund = cls._make_move(
            "out_refund",
            fields.Date.from_string("2026-09-22"),
            [(cls.armor_black, 1.0, 5.0, 0.0)],
            state="posted",
            hacienda="aceptado",
            salesperson=False,
        )
        cls.rejected_invoice = cls._make_move(
            "out_invoice",
            fields.Date.from_string("2026-09-23"),
            [(cls.armor_black, 1.0, 40.0, 0.0)],
            state="posted",
            hacienda="rechazado",
            salesperson=cls.salesperson,
        )
        cls.no_hacienda_invoice = cls._make_move(
            "out_invoice",
            fields.Date.from_string("2026-09-24"),
            [(cls.armor_black, 1.0, 15.0, 0.0)],
            state="posted",
            hacienda=False,
            salesperson=cls.salesperson,
        )
        cls.draft_invoice = cls._make_move(
            "out_invoice",
            fields.Date.from_string("2026-09-25"),
            [(cls.armor_black, 1.0, 10.0, 0.0)],
            state="draft",
            hacienda="aceptado",
            salesperson=cls.salesperson,
        )
        cls.cancelled_invoice = cls._make_move(
            "out_invoice",
            fields.Date.from_string("2026-09-26"),
            [(cls.armor_black, 1.0, 5.0, 0.0)],
            state="cancel",
            hacienda="aceptado",
            salesperson=cls.salesperson,
        )

    @classmethod
    def _variant_with_value(cls, template, value):
        return template.product_variant_ids.filtered(
            lambda product: value
            in product.product_template_attribute_value_ids.product_attribute_value_id
        )

    @classmethod
    def _make_move(
        cls,
        move_type,
        invoice_date,
        lines,
        state="draft",
        hacienda=False,
        salesperson=None,
        origin=None,
        company_data=None,
    ):
        company_data = company_data or cls.company_data
        company = company_data["company"]
        move = cls.env["account.move"].with_company(company).create(
            {
                "move_type": move_type,
                "invoice_date": invoice_date,
                "date": invoice_date,
                "company_id": company.id,
                "currency_id": company.currency_id.id,
                "partner_id": cls.partner_a.id,
                "payment_methods_id": cls.payment_method.id,
                "invoice_id": origin.id if origin else False,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": product.display_name,
                            "product_id": product.id,
                            "quantity": quantity,
                            "price_unit": price_unit,
                            "discount": discount,
                            "account_id": company_data["default_account_revenue"].id,
                            "tax_ids": [Command.clear()],
                        }
                    )
                    for product, quantity, price_unit, discount in lines
                ],
            }
        )
        if state == "posted":
            move.action_post()
        elif state == "cancel":
            move.button_cancel()
        move.write(
            {
                "state_tributacion": hacienda,
                "salesperson_id": salesperson.id if salesperson else False,
            }
        )
        return move

    def _wizard(self, attributes=None, values=None, **extra):
        values_dict = {
            "date_from": fields.Date.from_string("2026-09-01"),
            "date_to": fields.Date.from_string("2026-09-30"),
            "company_ids": [Command.set(self.env.company.ids)],
            "attribute_ids": [
                Command.set((attributes or (self.brand_attribute | self.color_attribute)).ids)
            ],
            "attribute_value_ids": [
                Command.set((values or (self.armor_value | self.black_value)).ids)
            ],
        }
        values_dict.update(extra)
        return self.env["sng.sales.attribute.report.wizard"].create(values_dict)

    def test_date_limits_and_incomplete_filters(self):
        self._wizard(
            date_from=fields.Date.from_string("2026-01-01"),
            date_to=fields.Date.from_string("2026-12-31"),
        )
        with self.assertRaises(ValidationError):
            self._wizard(
                date_from=fields.Date.from_string("2026-01-01"),
                date_to=fields.Date.from_string("2027-01-01"),
            )
        with self.assertRaises(ValidationError):
            self._wizard(
                attributes=self.brand_attribute | self.color_attribute,
                values=self.armor_value,
            )

        first_day = self._make_move(
            "out_invoice",
            fields.Date.from_string("2026-09-01"),
            [(self.armor_black, 1.0, 7.0, 0.0)],
            state="posted",
            hacienda="aceptado",
            salesperson=self.salesperson,
        )
        last_day = self._make_move(
            "out_invoice",
            fields.Date.from_string("2026-09-30"),
            [(self.armor_black, 1.0, 9.0, 0.0)],
            state="posted",
            hacienda="aceptado",
            salesperson=self.salesperson,
        )
        candidate_moves = self._wizard()._get_candidate_lines().move_id
        self.assertIn(first_day, candidate_moves)
        self.assertIn(last_day, candidate_moves)
        self.assertNotIn(self.origin_invoice, candidate_moves)

    def test_or_and_no_variant_and_archived_product(self):
        black_wizard = self._wizard()
        self.assertEqual(black_wizard._get_matching_products(), self.armor_black)

        both_colors = self._wizard(
            values=self.armor_value | self.black_value | self.red_value
        )
        self.assertEqual(
            set(both_colors._get_matching_products().ids),
            set((self.armor_black | self.armor_red).ids),
        )

        no_variant = self._wizard(
            attributes=self.catalog_attribute | self.color_attribute,
            values=self.promo_value | self.black_value,
        )
        self.assertEqual(no_variant._get_matching_products(), self.armor_black)

        self.armor_black.active = False
        self.assertEqual(black_wizard._get_matching_products(), self.armor_black)

    def test_accepted_totals_excluded_and_reconciliation(self):
        data = self._wizard()._get_report_data()
        self.assertEqual(len(data["groups"]), 1)
        group = data["groups"][0]
        totals = group["totals"]

        self.assertEqual(totals["invoice_count"], 2)
        self.assertEqual(totals["credit_note_count"], 2)
        self.assertAlmostEqual(totals["invoice_qty"], 3.0)
        self.assertAlmostEqual(totals["credit_qty"], 2.0)
        self.assertAlmostEqual(totals["invoice_total"], 190.0)
        self.assertAlmostEqual(totals["credit_total"], 25.0)
        self.assertAlmostEqual(totals["net_total"], 165.0)

        discounted_price = next(
            row for row in group["prices"] if row["price_unit"] == 100.0
        )
        self.assertAlmostEqual(discounted_price["discount"], 10.0)
        self.assertAlmostEqual(discounted_price["net_unit_price"], 90.0)
        self.assertAlmostEqual(discounted_price["total_unit_price"], 90.0)

        self.assertAlmostEqual(
            sum(row["net_total"] for row in group["salespersons"]),
            totals["net_total"],
        )
        self.assertAlmostEqual(
            sum(row["net_total"] for row in group["products"]),
            totals["net_total"],
        )
        detail_invoice = sum(
            row["company_total"]
            for row in group["details"]
            if row["move_type"] == "out_invoice"
        )
        detail_refund = sum(
            row["company_total"]
            for row in group["details"]
            if row["move_type"] == "out_refund"
        )
        self.assertAlmostEqual(detail_invoice - detail_refund, totals["net_total"])
        self.assertEqual(
            {row["salesperson_name"] for row in group["salespersons"]},
            {self.salesperson.display_name, "Sin vendedor"},
        )
        self.assertEqual(sum(row["document_count"] for row in group["excluded"]), 4)
        self.assertAlmostEqual(sum(row["total"] for row in group["excluded"]), 70.0)

    def test_credit_note_uses_own_date_and_origin_is_optional(self):
        data = self._wizard()._get_report_data()["groups"][0]
        notes = {row["credit_note_id"]: row for row in data["credit_notes"]}
        self.assertEqual(notes[self.linked_refund.id]["origin_move_id"], self.origin_invoice.id)
        self.assertEqual(notes[self.linked_refund.id]["credit_note_date"], "2026-09-20")
        self.assertFalse(notes[self.unlinked_refund.id]["origin_move_id"])
        self.assertNotIn(
            self.origin_invoice.id,
            {row["move_id"] for row in data["details"]},
        )

    def test_salesperson_filter_and_screen_links(self):
        wizard = self._wizard(
            salesperson_ids=[Command.set(self.salesperson.ids)]
        )
        data = wizard._get_report_data()["groups"][0]
        self.assertAlmostEqual(data["totals"]["invoice_total"], 180.0)
        self.assertAlmostEqual(data["totals"]["credit_total"], 20.0)
        action = wizard.action_view_on_screen()
        self.assertEqual(action["res_id"], wizard.id)
        self.assertTrue(wizard.show_results)
        self.assertEqual(len(wizard.salesperson_line_ids), 1)
        self.assertIn(
            self.accepted_invoice,
            wizard.salesperson_line_ids.move_ids,
        )
        self.assertEqual(len(wizard.product_line_ids), 1)
        self.assertEqual(len(wizard.credit_note_line_ids), 1)
        self.assertEqual(len(wizard.excluded_line_ids), 4)

    def test_multicompany_is_separated_and_access_is_respected(self):
        crc = self.env.ref("base.CRC")
        company_data_2 = self.setup_other_company(
            name="Compañía CRC reporte", currency_id=crc.id
        )
        self.env.user.company_ids = [Command.link(company_data_2["company"].id)]
        second_move = self._make_move(
            "out_invoice",
            fields.Date.from_string("2026-09-18"),
            [(self.armor_black, 1.0, 1000.0, 0.0)],
            state="posted",
            hacienda="aceptado",
            salesperson=self.salesperson,
            company_data=company_data_2,
        )
        wizard = self._wizard().with_context(
            allowed_company_ids=[self.env.company.id, company_data_2["company"].id]
        )
        wizard.company_ids = self.env.company | company_data_2["company"]
        groups = wizard._get_report_data()["groups"]
        self.assertEqual(len(groups), 2)
        self.assertEqual(
            {group["currency_name"] for group in groups},
            {self.env.company.currency_id.name, crc.name},
        )
        self.assertIn(second_move.id, groups[1]["totals"]["move_ids"])

        readonly_user = self.env["res.users"].create(
            {
                "name": "Lector del reporte",
                "login": "lector_atributos",
                "company_id": self.env.company.id,
                "company_ids": [Command.set(self.env.company.ids)],
                "groups_id": [Command.set(self.env.ref("account.group_account_readonly").ids)],
            }
        )
        restricted = wizard.with_user(readonly_user).with_context(
            allowed_company_ids=self.env.company.ids
        )
        self.assertEqual(restricted._get_selected_companies(), self.env.company)
        self.assertNotIn(second_move, restricted._get_candidate_lines().move_id)

    def test_xlsx_pdf_branding_and_currency_glyph(self):
        wizard = self._wizard()
        data = wizard._get_report_data()
        content = wizard._generate_xlsx(data)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            workbook_xml = archive.read("xl/workbook.xml").decode()
            styles_xml = archive.read("xl/styles.xml").decode()
            self.assertIn("Resumen", workbook_xml)
            self.assertIn("Resumen por producto", workbook_xml)
            self.assertIn("Auxiliar precios y descuentos", workbook_xml)
            self.assertIn("Detalle aceptado", workbook_xml)
            self.assertIn("Notas de crédito", workbook_xml)
            self.assertIn("Excluidos", workbook_xml)
            self.assertIn("Space Grotesk", styles_xml)
            self.assertTrue(any(name.startswith("xl/media/") for name in archive.namelist()))

        report = self.env.ref(
            "sng_sales_attribute_report.action_sales_attribute_report_pdf"
        )
        data["groups"][0]["currency_symbol"] = "₡"
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            report, wizard.ids, data={"report_data": data}
        )
        self.assertIn(b"#1BAAA0", html)
        self.assertIn(b"#F84E77", html)
        self.assertIn(b"Space Grotesk", html)
        self.assertIn(b"Currency Glyph", html)
        self.assertIn(b"data:image/png;base64,", html)
        self.assertIn(b"data:font/ttf;base64,", html)
        self.assertIn("₡".encode(), html)

        pdf, output_type = self.env["ir.actions.report"].with_context(
            force_report_rendering=True
        )._render_qweb_pdf(report, wizard.ids, data={"report_data": data})
        self.assertEqual(output_type, "pdf")
        self.assertTrue(pdf.startswith(b"%PDF"))
        pdf_text = "".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(pdf)).pages
        )
        # PyPDF2 2.x may expose wkhtmltopdf's UTF-8 bytes as Latin-1 code
        # points. Both forms prove that the glyph was not replaced by "?".
        self.assertTrue("₡" in pdf_text or "â‚¡" in pdf_text)
        self.assertNotIn("? 190.00", pdf_text)

        crc_font = file_path(
            "sng_sales_attribute_report/static/src/fonts/DejaVuSans.ttf"
        )
        self.assertTrue(os.path.isfile(crc_font))
