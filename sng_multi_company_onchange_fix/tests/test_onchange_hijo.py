# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOnchangeHijo(TransactionCase):
    """Crear un contacto hijo desde el formulario del padre (flujo del
    cliente web: onchange con el padre como diccionario y luego web_save)
    debe dejar al hijo en la compañía activa y legible para el usuario."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        cls.cia_a = Company.create({"name": "Cía A (prueba onchange)"})
        cls.cia_b = Company.create({"name": "Cía B (prueba onchange)"})
        cls.usuario = cls.env["res.users"].create({
            "name": "Usuario prueba onchange",
            "login": "prueba_onchange_hijo",
            "company_id": cls.cia_b.id,
            "company_ids": [(6, 0, [cls.cia_a.id, cls.cia_b.id])],
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("base.group_partner_manager").id,
                cls.env.ref("base.group_multi_company").id,
            ])],
        })
        # El padre pertenece a ambas compañías; A va primero.
        cls.padre = cls.env["res.partner"].create({
            "name": "Padre multi-compañía",
            "is_company": True,
            "company_ids": [(6, 0, [cls.cia_a.id, cls.cia_b.id])],
        })

    def _partner_como_usuario(self):
        # El usuario trabaja solo con la compañía B activa.
        return self.env["res.partner"].with_user(self.usuario).with_context(
            allowed_company_ids=[self.cia_b.id],
            default_parent_id=self.padre.id,
            default_type="other",
        )

    def test_onchange_padre_dict_devuelve_compania_activa(self):
        Partner = self._partner_como_usuario()
        spec = {
            "type": {},
            "name": {},
            "company_id": {"fields": {"display_name": {}}},
            "parent_id": {"fields": {"display_name": {}}},
        }
        # Así manda el padre el cliente web de Odoo 18 para líneas x2many.
        res = Partner.onchange({"parent_id": {"id": self.padre.id}}, [], spec)
        company = res["value"].get("company_id")
        self.assertTrue(company, "El onchange debe proponer una compañía")
        self.assertEqual(
            company["id"], self.cia_b.id,
            "El hijo debe proponer la compañía activa, no la primera del padre",
        )

    def test_web_save_hijo_legible(self):
        Partner = self._partner_como_usuario()
        res = Partner.onchange({"parent_id": {"id": self.padre.id}}, [], {
            "type": {}, "name": {},
            "company_id": {"fields": {"display_name": {}}},
        })
        vals = {"name": "Hijo prueba", "type": "other"}
        company = res["value"].get("company_id")
        if company:
            vals["company_id"] = company["id"]
        padre_usuario = self.padre.with_user(self.usuario).with_context(
            allowed_company_ids=[self.cia_b.id]
        )
        # Antes de la corrección esto lanzaba AccessError ("res.partner company").
        padre_usuario.web_save(
            {"child_ids": [[0, "virtual_1", vals]]},
            {"child_ids": {"fields": {"name": {}}}},
        )
        hijo = padre_usuario.child_ids.filtered(lambda p: p.name == "Hijo prueba")
        self.assertTrue(hijo, "El hijo debe ser legible por el usuario")
        self.assertEqual(hijo.sudo().company_ids, self.cia_a | self.cia_b,
                         "El hijo hereda las compañías del padre")

    def test_registro_real_sin_cambios(self):
        # Para registros reales el comportamiento original se mantiene.
        padre = self.padre.with_user(self.usuario).with_context(
            allowed_company_ids=[self.cia_b.id]
        )
        self.assertEqual(padre.company_id, self.cia_b)
        # ``company_ids`` se cachea por uid y la lectura no-sudo viene
        # filtrada por las reglas de res.company (comportamiento OCA previo),
        # así que hay que invalidar antes de cambiar las compañías activas.
        self.padre.invalidate_recordset()
        padre = self.padre.with_user(self.usuario).with_context(
            allowed_company_ids=[self.cia_a.id, self.cia_b.id]
        )
        self.assertEqual(padre.company_id, self.cia_a)
