from odoo import api, fields, models

from .sale_order_line import FORCE_GROUP, SKIP_CTX


class AccountMove(models.Model):
    _inherit = 'account.move'

    sng_pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Lista de precios',
        compute='_compute_sng_pricelist_id',
        store=True,
        readonly=False,
        precompute=True,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Lista usada para validar precios y descuentos de facturas manuales. "
             "En facturas creadas desde ventas prevalece la linea de pedido.",
    )

    @api.depends(
        'partner_id', 'company_id', 'move_type',
        'invoice_line_ids.sale_line_ids.order_id.pricelist_id',
    )
    def _compute_sng_pricelist_id(self):
        sale_types = ('out_invoice', 'out_refund', 'out_receipt')
        for move in self:
            if move.state and move.state != 'draft':
                continue
            if move.move_type not in sale_types or not move.partner_id:
                move.sng_pricelist_id = False
                continue
            source_pricelists = (
                move.invoice_line_ids.sale_line_ids.order_id.pricelist_id
            )
            if source_pricelists:
                move.sng_pricelist_id = source_pricelists[:1]
            else:
                company_move = move.with_company(move.company_id)
                move.sng_pricelist_id = (
                    company_move.partner_id.property_product_pricelist
                )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        # Durante la creacion anidada de invoice_line_ids la lista calculada
        # puede no estar disponible aun. Esta segunda barrera valida el
        # documento completo cuando ya terminaron todos los calculos del move.
        moves.invoice_line_ids._sng_check_invoice_price_lock(
            ('price_unit', 'discount')
        )
        return moves

    def write(self, vals):
        res = super().write(vals)
        pricing_basis = {
            'partner_id', 'company_id', 'move_type', 'sng_pricelist_id',
            'invoice_date', 'date', 'currency_id', 'fiscal_position_id',
        }
        if (
            pricing_basis.intersection(vals)
            and not self.env.context.get(SKIP_CTX)
            and not self.env.user.has_group(FORCE_GROUP)
        ):
            lines = self.invoice_line_ids
            lines._sng_reset_invoice_locked_values()
            lines._sng_check_invoice_price_lock(('price_unit', 'discount'))
        return res

    def _post(self, soft=True):
        self.invoice_line_ids._sng_check_invoice_price_lock(
            ('price_unit', 'discount')
        )
        return super()._post(soft=soft)
