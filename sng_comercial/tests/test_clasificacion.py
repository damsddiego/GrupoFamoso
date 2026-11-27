# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ComercialCommon


@tagged('post_install', '-at_install')
class TestClasificacion(ComercialCommon):

    def test_la_plantilla_toma_pilar_base_y_volumen(self):
        template = self._producto('Aceite clasificado', 'COM-CLA-1', self.pilar, self.base, self.vol_5).product_tmpl_id
        self.assertEqual(template.sng_pilar_id, self.pilar)
        self.assertEqual(template.sng_base_id, self.base)
        self.assertEqual(template.sng_volumen_id, self.vol_5)
        self.assertEqual(template.sng_litros_unidad, 5.0)

    def test_sin_atributos_queda_vacia(self):
        template = self._producto('Sin clasificar', 'COM-CLA-2').product_tmpl_id
        self.assertFalse(template.sng_pilar_id)
        self.assertFalse(template.sng_volumen_id)
        self.assertEqual(template.sng_litros_unidad, 0.0)

    def test_cambiar_el_valor_o_los_litros_recalcula(self):
        template = self._producto('Aceite cambia', 'COM-CLA-3', self.pilar, volumen=self.vol_5).product_tmpl_id
        linea_pilar = template.attribute_line_ids.filtered(lambda l: l.attribute_id == self.attr['pilar'])
        linea_pilar.value_ids = [Command.set(self.pilar_b.ids)]
        self.assertEqual(template.sng_pilar_id, self.pilar_b)

        self.vol_5.sng_litros = 4.73
        self.assertAlmostEqual(template.sng_litros_unidad, 4.73, places=3)

        linea_pilar.unlink()
        self.assertFalse(template.sng_pilar_id)

    def test_litros_propuestos_al_crear_el_valor(self):
        self.assertEqual(self.vol_5.sng_litros, 5.0)
        self.assertAlmostEqual(self.vol_400.sng_litros, 0.4, places=3)
        manual = self.env['product.attribute.value'].create({
            'name': 'Tambor test 55 gal', 'attribute_id': self.attr['volumen'].id, 'sng_litros': 208.0})
        self.assertEqual(manual.sng_litros, 208.0)

    def test_un_solo_atributo_por_uso(self):
        with self.assertRaises(ValidationError):
            self.env['product.attribute'].create({
                'name': 'Otro pilar', 'create_variant': 'no_variant', 'sng_comercial_rol': 'pilar'})

    def test_marcar_volumen_propone_litros(self):
        self.attr['volumen'].sng_comercial_rol = False
        self.vol_400.sng_litros = 0.0
        self.attr['volumen'].sng_comercial_rol = 'volumen'
        self.assertAlmostEqual(self.vol_400.sng_litros, 0.4, places=3)
