from odoo import api, fields, models

FORCE_GROUP = 'sng_sale_price_lock.group_sng_force_price'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sng_discount_locked = fields.Boolean(
        string='Descuento bloqueado',
        compute='_compute_sng_discount_locked',
        help="Tecnico: oculta el asistente de descuentos cuando el descuento "
             "debe provenir de la lista de precios.",
    )

    @api.depends('company_id', 'pricelist_id')
    @api.depends_context('uid')
    def _compute_sng_discount_locked(self):
        privileged = self.env.user.has_group(FORCE_GROUP)
        for order in self:
            company = order.company_id or order.env.company
            order.sng_discount_locked = (
                not privileged
                and bool(order.pricelist_id)
                and company.sng_lock_discount
            )
