from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_delivery_report_total(self):
        self.ensure_one()
        total = 0.0
        for move in self.move_ids_without_package:
            qty = move.quantity if self.state == "done" else move.product_uom_qty
            total += (qty or 0.0) * (move.price_unit or 0.0)
        return total

    def _get_delivery_report_taxes(self, move):
        self.ensure_one()
        taxes = move.product_id.taxes_id.filtered(
            lambda tax: not tax.company_id or tax.company_id == self.company_id
        )
        partner = self.partner_id or move.partner_id
        fiscal_position = partner.property_account_position_id if partner else False
        if fiscal_position:
            taxes = fiscal_position.map_tax(taxes)
        return taxes

    def _get_delivery_report_totals(self):
        self.ensure_one()
        currency = self.company_id.currency_id
        partner = self.partner_id or (
            self.move_ids_without_package and self.move_ids_without_package[0].partner_id
        )
        totals = {
            "qty_ordered": 0.0,
            "qty_delivered": 0.0,
            "subtotal": 0.0,
            "tax": 0.0,
            "total": 0.0,
        }
        for move in self.move_ids_without_package:
            qty_ordered = move.product_uom_qty or 0.0
            qty_delivered = move.quantity or 0.0
            qty_amount = qty_delivered if self.state == "done" else qty_ordered
            price_unit = move.price_unit or 0.0
            tax_result = self._get_delivery_report_taxes(move).compute_all(
                price_unit,
                currency=currency,
                quantity=qty_amount,
                product=move.product_id,
                partner=partner,
            )
            totals["qty_ordered"] += qty_ordered
            totals["qty_delivered"] += qty_delivered
            totals["subtotal"] += tax_result["total_excluded"]
            totals["tax"] += tax_result["total_included"] - tax_result["total_excluded"]
            totals["total"] += tax_result["total_included"]
        return totals

    @api.onchange('partner_id')
    def _onchange_partner_sale_locations(self):
        """
        Al seleccionar el contacto en el picking:
        - Solo aplica si el tipo de picking es transferencia entre bodegas.
        - La bodega de origen (`location_id`) se toma de la bodega del vendedor
          (res.users -> res.partner -> sale_location_id).
        - La bodega de destino (`location_dest_id`) se toma del contacto seleccionado
          (partner_id.sale_location_id).
        """
        for picking in self:

            if picking.picking_type_id.code != 'internal':
                continue

            if not picking.partner_id:
                continue

            user_sale_location = None
            if picking.partner_id.user_id:
                user_sale_location = picking.partner_id.user_id.partner_id.sale_location_id

            partner_sale_location = picking.partner_id.sale_location_id

            if user_sale_location:
                picking.location_id = user_sale_location

            if partner_sale_location:
                picking.location_dest_id = partner_sale_location
