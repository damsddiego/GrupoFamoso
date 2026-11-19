# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFacturaConSaldo(TransactionCase):
    """Una factura que estuvo pagada y volvió a quedar con saldo conserva sus
    líneas de comisión hasta que alguien la abre. Abrirla no puede fallar para
    un usuario sin permisos sobre las comisiones, y las líneas se eliminan en
    vez de quedar sueltas sin factura."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Commission = cls.env["sales.commission"]
        # Los esquemas de un mismo vendedor no pueden traslaparse, así que se
        # reutiliza el que exista y solo se crea uno si la base no tiene.
        cls.esquema = Commission.search([("commission_apply_on", "=", "invoice_payment")], limit=1)
        dominio = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("invoice_date", "!=", False),
            ("commission_analysis_line", "=", False),
        ]
        if cls.esquema:
            dominio += [
                ("company_id", "=", cls.esquema.company_id.id),
                ("salesperson_id", "in", cls.esquema.salesperson_ids.ids),
                ("invoice_date", ">=", cls.esquema.start_date),
                ("invoice_date", "<=", cls.esquema.end_date),
            ]
        cls.factura = cls.env["account.move"].search(dominio, order="id desc", limit=1)
        if not cls.factura:
            cls.skipTest(cls, "No hay una factura de cliente publicada con saldo pendiente.")
        cls.compania = cls.factura.company_id
        vendedor = cls.factura.salesperson_id or cls.factura.invoice_user_id.partner_id
        if not cls.esquema:
            cls.esquema = Commission.create({
                "name": "Esquema de prueba",
                "commission_type": "standard",
                "commission_apply_on": "invoice_payment",
                "standard_commission": 5,
                "start_date": cls.factura.invoice_date,
                "end_date": cls.factura.invoice_date,
                "company_id": cls.compania.id,
                "salesperson_ids": [(6, 0, vendedor.ids)],
            })
        # Línea que quedó de cuando la factura estuvo pagada.
        cls.linea = cls.env["sales.commission.analysis"].create({
            "name": "Comisión de prueba",
            "date": cls.factura.invoice_date,
            "sales_person_id": vendedor.id,
            "move_id": cls.factura.id,
            "commission_id": cls.esquema.id,
            "commission_type": cls.esquema.commission_type,
            "commission_amount": 100,
        })
        # Usuario de facturación sin ningún grupo de comisión de ventas.
        cls.usuario = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Usuario prueba factura con saldo",
            "login": "prueba_factura_con_saldo",
            "company_id": cls.compania.id,
            "company_ids": [(6, 0, cls.compania.ids)],
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("account.group_account_invoice").id,
            ])],
        })

    def _factura_como_usuario(self):
        return self.factura.with_user(self.usuario).with_context(
            allowed_company_ids=self.compania.ids)

    def test_usuario_sin_grupo_abre_la_factura(self):
        self.assertFalse(self.usuario.has_group("sales_commission_omax.group_sales_commission_user"))
        self.assertFalse(self.usuario.has_group("sales_commission_omax.group_sales_commission_manager"))
        valores = self._factura_como_usuario().web_read({"invoice_payments_widget": {}})
        self.assertIn("invoice_payments_widget", valores[0])
        # La línea se elimina: no queda ni en la factura ni suelta.
        self.assertFalse(self.linea.exists())

    def test_varias_facturas_a_la_vez(self):
        # Con otras facturas en el mismo lote el widget se calcula para todas.
        otras = self.env["account.move"].search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("company_id", "=", self.compania.id),
            ("id", "!=", self.factura.id),
        ], order="id desc", limit=3)
        facturas = (self.factura | otras).with_user(self.usuario).with_context(
            allowed_company_ids=self.compania.ids)
        valores = facturas.web_read({"invoice_payments_widget": {}})
        self.assertEqual(len(valores), len(facturas))
        self.assertFalse(self.linea.exists())

    def test_onchange_no_toca_la_base(self):
        # En un onchange la factura es un registro virtual: no se borra nada.
        virtual = self.env["account.move"].with_user(self.usuario).with_context(
            allowed_company_ids=self.compania.ids).new(origin=self._factura_como_usuario())
        virtual.invoice_payments_widget
        self.assertTrue(self.linea.exists())
        self.assertEqual(self.linea.move_id, self.factura)
