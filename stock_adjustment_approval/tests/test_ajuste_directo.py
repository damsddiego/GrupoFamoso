from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

GRUPO_DIRECTO = 'stock_adjustment_approval.group_stock_ajuste_directo'
SOLICITANTE = 'stock_adjustment_approval.group_stock_adjustment_requester'
APROBADOR = 'stock_adjustment_approval.group_stock_adjustment_approver'


@tagged('post_install', '-at_install')
class TestAjusteDirecto(TransactionCase):
    """Ajustar cantidades sin solicitud solo con el grupo; nadie se aprueba a sí mismo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1,
        )
        cls.location = cls.warehouse.lot_stock_id
        cls.product = cls.env['product.product'].create({
            'name': 'Producto para ajuste directo',
            'is_storable': True,
        })
        cls.env['stock.quant']._update_available_quantity(cls.product, cls.location, 10.0)
        cls.jefe = cls._usuario('jefe-bodega', 'stock.group_stock_manager', SOLICITANTE, APROBADOR)
        cls.aprobador = cls._usuario('contabilidad-prueba', 'stock.group_stock_user', APROBADOR)
        cls.solicitante = cls._usuario('bodega-prueba', 'stock.group_stock_user', SOLICITANTE)
        cls.admin = cls._usuario(
            'admin-inventario', 'stock.group_stock_manager', SOLICITANTE, APROBADOR, GRUPO_DIRECTO,
        )

    @classmethod
    def _usuario(cls, login, *grupos):
        return cls.env['res.users'].create({
            'name': login,
            'login': login,
            'email': '%s@example.com' % login,
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'groups_id': [(6, 0, [cls.env.ref(grupo).id for grupo in grupos])],
        })

    def _stock(self):
        return self.env['stock.quant']._get_available_quantity(self.product, self.location)

    def _quant(self, user):
        return self.env['stock.quant'].with_user(user).with_context(inventory_mode=True).search([
            ('product_id', '=', self.product.id), ('location_id', '=', self.location.id),
        ])

    def _solicitud(self, user, cantidad=-2.0):
        request = self.env['stock.adjustment.request'].with_user(user).create({
            'reason': 'Conteo de prueba',
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'location_id': self.location.id,
                'adjustment_quantity': cantidad,
            })],
        })
        request.action_submit()
        return request

    # ------------------------------------------------------------------
    # Ajuste directo de cantidades
    # ------------------------------------------------------------------

    def test_jefe_de_bodega_sin_grupo_no_actualiza_cantidad(self):
        quant = self._quant(self.jefe)

        with self.assertRaisesRegex(AccessError, 'solicitud de ajuste'):
            quant.inventory_quantity_auto_apply = 4.0

        self.assertEqual(self._stock(), 10.0)

    def test_jefe_de_bodega_sin_grupo_no_aplica_conteo_fisico(self):
        quant = self._quant(self.jefe)
        quant.inventory_quantity = 7.0

        with self.assertRaisesRegex(AccessError, 'solicitud de ajuste'):
            quant.action_apply_inventory()

        self.assertEqual(self._stock(), 10.0)

    def test_jefe_de_bodega_sin_grupo_no_crea_existencias_nuevas(self):
        otra = self.env['stock.location'].create({
            'name': 'Estante sin existencias',
            'usage': 'internal',
            'location_id': self.location.id,
        })

        with self.assertRaisesRegex(AccessError, 'solicitud de ajuste'):
            self.env['stock.quant'].with_user(self.jefe).with_context(inventory_mode=True).create({
                'product_id': self.product.id,
                'location_id': otra.id,
                'inventory_quantity_auto_apply': 5.0,
            })

        self.assertEqual(
            self.env['stock.quant']._get_available_quantity(self.product, otra), 0.0,
        )

    def test_asistente_de_cantidad_del_producto_tambien_exige_el_grupo(self):
        wizard = self.env['stock.change.product.qty'].with_user(self.jefe).create({
            'product_id': self.product.id,
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'new_quantity': 3.0,
        })

        with self.assertRaisesRegex(AccessError, 'solicitud de ajuste'):
            wizard.change_product_qty()

        self.assertEqual(self._stock(), 10.0)

    def test_usuario_con_grupo_actualiza_cantidad(self):
        quant = self._quant(self.admin)

        quant.inventory_quantity_auto_apply = 4.0

        self.assertEqual(self._stock(), 4.0)

    def test_aprobar_una_solicitud_sigue_aplicando_el_ajuste(self):
        request = self._solicitud(self.solicitante)

        request.with_user(self.aprobador).action_approve()

        self.assertEqual(request.state, 'approved')
        self.assertEqual(self._stock(), 8.0)
        self.assertTrue(request.line_ids.move_ids.is_inventory)

    def test_boton_actualizar_cantidad_se_oculta_sin_el_grupo(self):
        Template = self.env['product.template']

        sin_grupo = Template.with_user(self.jefe).get_view(view_type='form')['arch']
        con_grupo = Template.with_user(self.admin).get_view(view_type='form')['arch']

        self.assertNotIn('string="Update Quantity"', sin_grupo)
        self.assertNotIn('string="Actualizar cantidad"', sin_grupo)
        self.assertTrue(
            'string="Update Quantity"' in con_grupo or 'string="Actualizar cantidad"' in con_grupo
        )

    def test_lista_de_existencias_es_de_solo_lectura_sin_el_grupo(self):
        editable = self.env.ref('stock.view_stock_quant_tree_editable').id

        sin_grupo = self.product.with_user(self.jefe).action_open_quants()
        con_grupo = self.product.with_user(self.admin).action_open_quants()

        self.assertNotEqual(sin_grupo['view_id'], editable)
        self.assertFalse(sin_grupo['context'].get('inventory_mode'))
        self.assertEqual(con_grupo['view_id'], editable)

    # ------------------------------------------------------------------
    # Quien pide no aprueba
    # ------------------------------------------------------------------

    def test_quien_pide_no_aprueba_su_propia_solicitud(self):
        request = self._solicitud(self.jefe)

        with self.assertRaisesRegex(UserError, 'otra persona'):
            request.with_user(self.jefe).action_approve()

        self.assertEqual(request.state, 'submitted')
        self.assertEqual(self._stock(), 10.0)

    def test_el_grupo_de_ajuste_directo_tampoco_se_aprueba_a_si_mismo(self):
        request = self._solicitud(self.admin)

        with self.assertRaisesRegex(UserError, 'otra persona'):
            request.with_user(self.admin).action_approve()

    def test_otro_aprobador_si_aprueba(self):
        request = self._solicitud(self.jefe)

        request.with_user(self.aprobador).action_approve()

        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.approved_by, self.aprobador)
        self.assertEqual(self._stock(), 8.0)
