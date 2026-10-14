from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAsientoSinActividad(TransactionCase):

    def _field_node(self):
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        nodes = etree.fromstring(arch).xpath("//field[@name='economic_activity_id']")
        self.assertTrue(nodes, "economic_activity_id no esta en el formulario")
        return nodes[0]

    def test_asiento_no_requiere_actividad(self):
        node = self._field_node()
        self.assertIn("move_type != 'entry'", node.get("required"))
        self.assertIn("move_type == 'entry'", node.get("invisible"))

    def test_facturas_siguen_requiriendo_actividad(self):
        required = self._field_node().get("required")
        self.assertIn("move_type in ('out_invoice', 'out_refund')", required)
        self.assertIn("tipo_documento in ('FE', 'FEC')", required)
