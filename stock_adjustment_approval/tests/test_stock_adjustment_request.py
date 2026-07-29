from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestStockAdjustmentRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location = cls.env['stock.warehouse'].search([
            ('company_id', '=', cls.env.company.id),
        ], limit=1).lot_stock_id
        cls.product = cls.env['product.product'].create({
            'name': 'Producto con lote',
            'is_storable': True,
            'tracking': 'lot',
        })
        cls.lot = cls.env['stock.lot'].create({
            'name': 'LOTE-UNICO',
            'product_id': cls.product.id,
            'company_id': cls.env.company.id,
        })
        cls.env['stock.quant'].create({
            'product_id': cls.product.id,
            'location_id': cls.location.id,
            'lot_id': cls.lot.id,
            'quantity': 1.0,
        })
        cls.request = cls.env['stock.adjustment.request'].create({})

    def _create_line(self, **values):
        return self.env['stock.adjustment.request.line'].create({
            'request_id': self.request.id,
            'product_id': self.product.id,
            'location_id': self.location.id,
            'counted_quantity': 1.0,
            **values,
        })

    def test_submission_assigns_the_only_existing_lot(self):
        line = self._create_line()

        line._validate_for_submission()

        self.assertEqual(line.lot_id, self.lot)

    def test_submission_requires_selection_when_multiple_lots_exist(self):
        second_lot = self.env['stock.lot'].create({
            'name': 'LOTE-SEGUNDO',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'lot_id': second_lot.id,
            'quantity': 1.0,
        })
        line = self._create_line()

        with self.assertRaises(UserError):
            line._validate_for_submission()

        self.assertFalse(line.lot_id)
