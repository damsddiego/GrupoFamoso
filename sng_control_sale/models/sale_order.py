import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)

_TEMPORARY_PRICELIST_COMPANY_FIXES = {
    # Temporary XML-RPC import patch: SAASA default pricelist sent for
    # company 2 must be replaced before record rules try to read it.
    (2, 17): 16,
}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    can_revert_to_editable = fields.Boolean(
        compute='_compute_can_revert_to_editable',
        string='Puede reversarse para edicion',
    )

    def _sng_context_for_company(self, company):
        allowed_company_ids = list(self.env.context.get('allowed_company_ids') or [])
        if company.id not in allowed_company_ids:
            allowed_company_ids.insert(0, company.id)
        return dict(
            self.env.context,
            allowed_company_ids=allowed_company_ids,
        )

    def _sng_pricelist_matches_company(self, pricelist, company):
        if not pricelist:
            return True
        pricelist_company = pricelist.sudo().company_id
        return not pricelist_company or pricelist_company == company

    def _sng_temporary_pricelist_company_fix(self, vals, company_id):
        pricelist_id = vals.get('pricelist_id')
        replacement_id = _TEMPORARY_PRICELIST_COMPANY_FIXES.get(
            (company_id, pricelist_id)
        )
        if not replacement_id:
            return vals

        vals = dict(vals)
        vals['pricelist_id'] = replacement_id
        _logger.warning(
            '[sng_control_sale] Temporary XML-RPC pricelist fix: '
            'company_id=%s pricelist_id=%s replaced with %s',
            company_id,
            pricelist_id,
            replacement_id,
        )
        return vals

    def _sng_company_pricelist(self, company, partner=False):
        company_context = self._sng_context_for_company(company)
        Pricelist = self.env['product.pricelist'].with_context(
            company_context
        ).with_company(company)
        if partner:
            partner_pricelist = partner.with_context(
                company_context
            ).with_company(company).property_product_pricelist
            if self._sng_pricelist_matches_company(partner_pricelist, company):
                return partner_pricelist
        return Pricelist.search([
            ('company_id', 'in', (False, company.id)),
            ('active', '=', True),
        ], limit=1)

    def _sng_sale_pricelist_vals(self, vals, order=False):
        if not {'company_id', 'partner_id', 'pricelist_id'} & set(vals):
            return vals

        company_id = (
            vals.get('company_id')
            or (order.company_id.id if order else False)
            or self.env.company.id
        )
        if not company_id:
            return vals

        vals = self._sng_temporary_pricelist_company_fix(vals, company_id)
        company = self.env['res.company'].browse(company_id)
        company_context = self._sng_context_for_company(company)
        partner_id = vals.get('partner_id') or (order.partner_id.id if order else False)
        partner = (
            self.env['res.partner'].with_context(company_context).browse(partner_id)
            if partner_id else False
        )
        pricelist_id = vals.get('pricelist_id')

        if pricelist_id is None and order:
            pricelist = order.pricelist_id
        elif pricelist_id:
            pricelist = self.env['product.pricelist'].with_context(
                company_context
            ).browse(pricelist_id)
        else:
            pricelist = False

        if self._sng_pricelist_matches_company(pricelist, company):
            return vals

        fixed_pricelist = self._sng_company_pricelist(company, partner)
        vals = dict(vals)
        vals['pricelist_id'] = fixed_pricelist.id or False
        return vals

    @api.onchange('company_id', 'partner_id', 'pricelist_id')
    def _onchange_sng_pricelist_company(self):
        for order in self:
            if not order.company_id or self._sng_pricelist_matches_company(
                order.pricelist_id,
                order.company_id,
            ):
                continue
            order.pricelist_id = order._sng_company_pricelist(
                order.company_id,
                order.partner_id,
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for vals in vals_list:
            vals = self._sng_sale_pricelist_vals(vals)
            company_id = vals.get('company_id')
            if company_id:
                company = self.env['res.company'].browse(company_id)
                records |= super(
                    SaleOrder,
                    self.with_context(self._sng_context_for_company(company)),
                ).create([vals])
            else:
                records |= super(SaleOrder, self).create([vals])
        return records

    def write(self, vals):
        if vals.get('state') == 'sale' and not self.env.context.get('skip_stock_block'):
            for order in self:
                message = order._stock_confirmation_error_message()
                if message:
                    raise UserError(message)

        if {'company_id', 'partner_id', 'pricelist_id'} & set(vals):
            result = True
            for order in self:
                company_id = vals.get('company_id') or order.company_id.id
                company = self.env['res.company'].browse(company_id)
                order_ctx = order.with_context(order._sng_context_for_company(company))
                fixed_vals = order_ctx._sng_sale_pricelist_vals(vals, order=order_ctx)
                result = super(SaleOrder, order_ctx).write(fixed_vals) and result
            return result

        return super().write(vals)

    def _action_confirm(self):
        self._check_stock_before_confirm()
        return super()._action_confirm()

    def _confirmation_error_message(self):
        error = super()._confirmation_error_message()
        if error:
            return error
        return self._stock_confirmation_error_message()

    def _check_stock_before_confirm(self):
        for order in self:
            message = order._stock_confirmation_error_message()
            if message:
                raise UserError(message)

    def _stock_confirmation_error_message(self):
        self.ensure_one()
        company = self.company_id
        if not company.block_sale_without_stock:
            return False
        if company.stock_block_allow_exception_group and self.env.user.has_group(
            'sng_control_sale.group_allow_negative_stock'
        ):
            return False
        if company.stock_block_warehouse_ids and self.warehouse_id not in company.stock_block_warehouse_ids:
            return False

        required_by_product = {}
        for line in self.order_line:
            product = line.product_id
            if not product or line.product_uom_qty <= 0.0:
                continue
            # Odoo 18: use is_storable instead of type == 'product'
            if not product.is_storable:
                continue
            qty = line.product_uom._compute_quantity(
                line.product_uom_qty,
                product.uom_id,
            )
            if qty <= 0.0:
                continue
            required_by_product[product.id] = required_by_product.get(product.id, 0.0) + qty

        if not required_by_product:
            return False

        products = self.env['product.product'].browse(list(required_by_product))
        products = products.with_company(company).with_context(warehouse=self.warehouse_id.id)
        available_by_product = {product.id: product.free_qty for product in products}

        insufficient = []
        for product in products:
            required_qty = required_by_product.get(product.id, 0.0)
            available_qty = available_by_product.get(product.id, 0.0)
            if float_compare(
                required_qty,
                available_qty,
                precision_rounding=product.uom_id.rounding,
            ) > 0:
                insufficient.append((product, required_qty, available_qty))

        if not insufficient:
            return False

        message_lines = [
            _('No hay stock suficiente para confirmar la orden:'),
        ]
        for product, required_qty, available_qty in insufficient:
            message_lines.extend([
                _('Producto: %s') % product.display_name,
                _('Solicitado: %s %s') % (required_qty, product.uom_id.display_name),
                _('Disponible (sin reservas) en Almacén %s: %s %s') % (
                    self.warehouse_id.display_name,
                    available_qty,
                    product.uom_id.display_name,
                ),
                '',
            ])
        return '\n'.join(message_lines).strip()

    @api.constrains('state', 'order_line', 'warehouse_id', 'company_id')
    def _check_stock_on_state_sale(self):
        for order in self:
            if order.state != 'sale':
                continue
            message = order._stock_confirmation_error_message()
            if message:
                raise ValidationError(message)

    @api.depends('state', 'locked', 'invoice_ids.state', 'picking_ids.state')
    def _compute_can_revert_to_editable(self):
        for order in self:
            try:
                blockers = order._stringify_blockers(order._get_revert_to_editable_blockers())
                order.can_revert_to_editable = not blockers
            except Exception:
                _logger.exception(
                    '[sng_control_sale] Error calculando can_revert_to_editable para sale.order id=%s',
                    order.id,
                )
                order.can_revert_to_editable = False

    def _get_record_labels(self, records):
        labels = []
        for record in records:
            labels.append(str(record.display_name or record.id))
        return ', '.join(labels)

    def _stringify_blockers(self, blockers):
        if not blockers:
            return []
        return [str(blocker) for blocker in blockers if blocker]

    def _get_revert_to_editable_blockers(self):
        self.ensure_one()
        allowed_states = {'sales_approval', 'finance_approval', 'approved', 'reject', 'sale'}
        if self.state not in allowed_states:
            return ['La orden solo se puede reversar desde un estado aprobado o confirmado.']

        blockers = []
        active_invoices = self.invoice_ids.filtered(lambda invoice: invoice.state != 'cancel')
        if active_invoices:
            blockers.append(
                'La orden tiene facturas activas: %s' % self._get_record_labels(active_invoices)
            )

        active_pickings = self.picking_ids.filtered(lambda picking: picking.state != 'cancel')
        if active_pickings:
            blockers.append(
                'La orden tiene entregas activas: %s' % self._get_record_labels(active_pickings)
            )

        return blockers

    def action_revert_to_editable(self):
        for order in self:
            blockers = order._stringify_blockers(order._get_revert_to_editable_blockers())
            if blockers:
                raise UserError(
                    'No se puede reversar la orden para editarla:\n%s' % '\n'.join(blockers)
                )

        approval_orders = self.filtered(
            lambda order: order.state in {'sales_approval', 'finance_approval', 'approved', 'reject'}
        )
        if approval_orders:
            approval_vals = {
                'state': 'draft',
                'signature': False,
                'signed_by': False,
                'signed_on': False,
            }
            if 'is_credit_limit_final_approved' in approval_orders._fields:
                approval_vals['is_credit_limit_final_approved'] = False
            approval_orders.write(approval_vals)
            for order in approval_orders:
                order.message_post(body=_('Orden reversada a cotizacion para edicion.'))

        confirmed_orders = self.filtered(lambda order: order.state == 'sale')
        if confirmed_orders:
            confirmed_orders.write({
                'state': 'draft',
                'locked': False,
                'signature': False,
                'signed_by': False,
                'signed_on': False,
            })
            for order in confirmed_orders:
                order.message_post(body=_('Orden reversada a cotizacion para edicion.'))

        return True
