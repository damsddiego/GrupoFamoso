import logging

from datetime import date

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


TEMP_COMPANY_CHECK_BYPASS_DATES = {
    date(2026, 5, 26),
    date(2026, 5, 27),
}
TEMP_COMPANY_CHECK_BYPASS_COMPANY_ID = 2
TEMP_COMPANY_CHECK_BYPASS_FIELDS = {
    "partner_id",
    "partner_invoice_id",
    "partner_shipping_id",
}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    assigned_salesperson_id = fields.Many2one(
        "res.partner",
        string="Assigned Salesperson",
        compute="_compute_assigned_salesperson_id",
        store=True,
        readonly=True,
        help="The salesperson assigned to this customer.",
    )

    def _check_company(self, fnames=None):
        today = fields.Date.context_today(self)
        if today not in TEMP_COMPANY_CHECK_BYPASS_DATES:
            return super()._check_company(fnames=fnames)

        bypass_orders = self.filtered(
            lambda order: order.company_id.id == TEMP_COMPANY_CHECK_BYPASS_COMPANY_ID
        )
        regular_orders = self - bypass_orders

        if regular_orders:
            super(SaleOrder, regular_orders)._check_company(fnames=fnames)

        if not bypass_orders:
            return

        if fnames is None or {"company_id", "company_ids"} & set(fnames):
            checked_fields = set(self._fields)
        else:
            checked_fields = set(fnames)

        remaining_fields = list(checked_fields - TEMP_COMPANY_CHECK_BYPASS_FIELDS)
        if remaining_fields:
            super(SaleOrder, bypass_orders)._check_company(fnames=remaining_fields)

        _logger.warning(
            "Temporary company check bypass applied on %s for sale.order ids %s "
            "in company %s. Skipped fields: %s",
            sorted(TEMP_COMPANY_CHECK_BYPASS_DATES),
            bypass_orders.ids,
            TEMP_COMPANY_CHECK_BYPASS_COMPANY_ID,
            sorted(TEMP_COMPANY_CHECK_BYPASS_FIELDS),
        )

    @api.depends('partner_id', 'company_id')
    def _compute_assigned_salesperson_id(self):
        for order in self:
            if order.partner_id and order.company_id:
                order.assigned_salesperson_id = order.partner_id.with_company(order.company_id).assigned_salesperson_id
            else:
                order.assigned_salesperson_id = False
