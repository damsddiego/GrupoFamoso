from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestAplicarDiferencia(TransactionCase):
    """El usuario escribe el ajuste con signo (-5 resta cinco, +1 suma uno) y al aprobar
    se aplica ese ajuste sobre el stock de hoy, no una cantidad absoluta.

    Casos reales: SAI2026100109 y SAI2026090069 (G-YTX7L-BS, Protire), aprobadas
    días después de enviadas, sumaron +219 cuando se habían pedido -2.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref(
            'stock_adjustment_approval.group_stock_adjustment_approver'
        )
        cls.Quant = cls.env['stock.quant']
        cls.location = cls.env['stock.warehouse'].search([
            ('company_id', '=', cls.env.company.id),
        ], limit=1).lot_stock_id
        cls.product = cls.env['product.product'].create({
            'name': 'Batería de prueba',
            'is_storable': True,
        })
        cls.Quant._update_available_quantity(cls.product, cls.location, 504.0)

    def _request(self, *lines):
        return self.env['stock.adjustment.request'].create({
            'reason': 'GARANTIA PRUEBA',
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'location_id': self.location.id,
                **values,
            }) for values in lines],
        })

    def _stock(self, product=None, lot=None):
        quants = self.Quant._gather(
            product or self.product, self.location, lot_id=lot, strict=True,
        ).filtered(lambda q: q.lot_id == (lot or self.env['stock.lot']))
        return sum(quants.mapped('quantity'))

    def _sell(self, qty, product=None, lot=None):
        self.Quant._update_available_quantity(
            product or self.product, self.location, -qty, lot_id=lot,
        )

    def test_venta_entre_envio_y_aprobacion_aplica_solo_la_diferencia(self):
        request = self._request({'adjustment_quantity': -1.0})
        request.action_submit()
        line = request.line_ids
        self.assertEqual(line.theoretical_quantity, 504.0)
        self.assertEqual(line.counted_quantity, 503.0)

        self._sell(20.0)
        line.invalidate_recordset()
        self.assertEqual(line.current_quantity, 484.0)
        self.assertEqual(line.adjustment_quantity, -1.0)
        self.assertEqual(line.projected_quantity, 483.0)
        self.assertTrue(line.stock_changed)
        self.assertTrue(request.stock_changed)

        request.action_approve()

        self.assertEqual(self._stock(), 483.0)
        self.assertEqual(line.quantity_at_approval, 484.0)
        self.assertEqual(line.applied_difference, -1.0)
        move = line.move_ids
        self.assertEqual(len(move), 1)
        self.assertEqual(move.quantity, 1.0)
        self.assertEqual(move.location_id, self.location)

    def test_dos_solicitudes_del_mismo_producto_suman_sus_diferencias(self):
        old = self._request({'adjustment_quantity': -1.0})
        old.action_submit()
        self._sell(200.0)
        new = self._request({'adjustment_quantity': -1.0})
        new.action_submit()
        self.assertEqual(new.line_ids.theoretical_quantity, 304.0)
        self._sell(20.0)

        new.action_approve()
        old.action_approve()

        self.assertEqual(self._stock(), 282.0)

    def test_sin_cambios_de_stock_no_marca_aviso(self):
        request = self._request({'adjustment_quantity': -1.0})
        request.action_submit()

        self.assertFalse(request.line_ids.stock_changed)
        self.assertFalse(request.stock_changed)
        self.assertEqual(request.line_ids.projected_quantity, 503.0)

    def test_ajuste_positivo_suma(self):
        request = self._request({'adjustment_quantity': 5.0})
        request.action_submit()

        request.action_approve()

        self.assertEqual(self._stock(), 509.0)
        self.assertEqual(request.line_ids.applied_difference, 5.0)

    def test_ajuste_cero_no_se_puede_enviar(self):
        request = self._request({'adjustment_quantity': 0.0})

        with self.assertRaises(UserError):
            request.action_submit()

    def test_no_se_puede_enviar_si_el_stock_quedaria_negativo(self):
        request = self._request({'adjustment_quantity': -505.0})

        with self.assertRaises(UserError):
            request.action_submit()

    def test_no_se_puede_aprobar_si_el_stock_quedaria_negativo(self):
        request = self._request({'adjustment_quantity': -500.0})
        request.action_submit()
        self._sell(10.0)

        with self.assertRaises(UserError):
            request.action_approve()

        self.assertEqual(request.state, 'submitted')
        self.assertEqual(self._stock(), 494.0)

    def test_lote_solo_toca_el_quant_del_lote(self):
        product = self.env['product.product'].create({
            'name': 'Producto con lote',
            'is_storable': True,
            'tracking': 'lot',
        })
        lot = self.env['stock.lot'].create({
            'name': 'LOTE-A',
            'product_id': product.id,
            'company_id': self.env.company.id,
        })
        self.Quant._update_available_quantity(product, self.location, 5.0, lot_id=lot)
        self.Quant._update_available_quantity(product, self.location, 3.0)
        request = self.env['stock.adjustment.request'].create({
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'location_id': self.location.id,
                'lot_id': lot.id,
                'adjustment_quantity': -1.0,
            })],
        })
        request.action_submit()
        self.assertEqual(request.line_ids.theoretical_quantity, 5.0)

        request.action_approve()

        self.assertEqual(self._stock(product, lot), 4.0)
        self.assertEqual(self._stock(product), 3.0)
        self.assertEqual(request.line_ids.move_ids.move_line_ids.lot_id, lot)

    def test_linea_duplicada_no_se_permite(self):
        with self.assertRaises(ValidationError):
            self._request({'adjustment_quantity': -1.0}, {'adjustment_quantity': -4.0})

    def test_no_vincula_movimientos_ajenos(self):
        other_location = self.env['stock.location'].create({
            'name': 'Otra ubicación',
            'usage': 'internal',
            'location_id': self.location.id,
        })
        self.Quant._update_available_quantity(self.product, other_location, 10.0)
        request = self._request({'adjustment_quantity': -1.0})
        request.action_submit()

        Quant = type(self.Quant)
        original = Quant._apply_inventory

        def apply_and_someone_else_counts(quants):
            original(quants)
            other = self.Quant._gather(self.product, other_location, strict=True)
            other.inventory_quantity = 7.0
            original(other)

        with patch.object(Quant, '_apply_inventory', apply_and_someone_else_counts):
            request.action_approve()

        moves = request.line_ids.move_ids
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.location_id, self.location)
