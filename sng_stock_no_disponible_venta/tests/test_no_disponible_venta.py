# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged

from ..models.product_product import CLAVE_CONTEXTO, cambiar_campo


@tagged('post_install', '-at_install')
class TestNoDisponibleVenta(TransactionCase):
    """Un almacén con Existencias (10) y, al lado, Malo (4)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.almacen = cls.env['stock.warehouse'].create({'name': 'Prueba NDV', 'code': 'NDV'})
        cls.existencias = cls.almacen.lot_stock_id
        cls.malo = cls.env['stock.location'].create({
            'name': 'Malo',
            'usage': 'internal',
            'location_id': cls.almacen.view_location_id.id,
        })
        cls.producto = cls.env['product.product'].create({
            'name': 'Producto NDV', 'type': 'consu', 'is_storable': True,
        })
        Quant = cls.env['stock.quant']
        Quant._update_available_quantity(cls.producto, cls.existencias, 10)
        Quant._update_available_quantity(cls.producto, cls.malo, 4)

    def _leer(self, campo, excluir=False):
        # free_qty se cachea por transacción y la clave de contexto no es parte
        # de la llave de caché: sin invalidar, la segunda lectura repetiría la primera.
        self.env.invalidate_all()
        contexto = {'warehouse_id': self.almacen.id}
        if excluir:
            contexto[CLAVE_CONTEXTO] = True
        return self.producto.with_context(**contexto)[campo]

    def test_sin_ubicaciones_marcadas_no_cambia_nada(self):
        self.assertEqual(self._leer('free_qty', excluir=True), 14)

    def test_marcada_sin_la_clave_de_contexto_no_cambia_nada(self):
        self.malo.sng_no_disponible_venta = True
        self.assertEqual(self._leer('free_qty'), 14)
        self.assertEqual(self._leer('qty_available'), 14)

    def test_marcada_con_la_clave_se_excluye(self):
        self.malo.sng_no_disponible_venta = True
        self.assertEqual(self._leer('free_qty', excluir=True), 10)
        self.assertEqual(self._leer('qty_available', excluir=True), 10)

    def test_marcar_la_vista_excluye_todo_el_almacen(self):
        self.almacen.view_location_id.sng_no_disponible_venta = True
        self.assertEqual(self._leer('free_qty', excluir=True), 0)

    def test_movimiento_desde_malo_cuenta_como_entrada(self):
        movimiento = self.env['stock.move'].create({
            'name': 'Reparado a existencias',
            'product_id': self.producto.id,
            'product_uom_qty': 3,
            'product_uom': self.producto.uom_id.id,
            'location_id': self.malo.id,
            'location_dest_id': self.existencias.id,
        })
        movimiento._action_confirm()
        self.malo.sng_no_disponible_venta = True
        # Sin la clave es un movimiento interno del almacén: no es entrada.
        self.assertEqual(self._leer('incoming_qty'), 0)
        self.assertEqual(self._leer('incoming_qty', excluir=True), 3)

    def test_movimiento_hacia_malo_cuenta_como_salida(self):
        movimiento = self.env['stock.move'].create({
            'name': 'Dañado',
            'product_id': self.producto.id,
            'product_uom_qty': 2,
            'product_uom': self.producto.uom_id.id,
            'location_id': self.existencias.id,
            'location_dest_id': self.malo.id,
        })
        movimiento._action_confirm()
        self.malo.sng_no_disponible_venta = True
        self.assertEqual(self._leer('outgoing_qty'), 0)
        self.assertEqual(self._leer('outgoing_qty', excluir=True), 2)

    def test_cambiar_campo_respeta_operadores_y_hojas_especiales(self):
        dominio = ['|', ('location_id.parent_path', '=like', '1/%'),
                   ('location_id', '=', 5), (0, '=', 1)]
        self.assertEqual(
            cambiar_campo(dominio, 'location_id', 'location_dest_id'),
            ['|', ('location_dest_id.parent_path', '=like', '1/%'),
             ('location_dest_id', '=', 5), (0, '=', 1)])
