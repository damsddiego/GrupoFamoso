from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _sng_assign_default_receivable_accounts(self, companies=None):
        companies = companies or self.env.companies
        customer_partners = self
        if not customer_partners:
            customer_partners = self.with_context(active_test=False).search([
                ("customer_rank", ">", 0),
                ("parent_id", "=", False),
            ])
        else:
            customer_partners = customer_partners.filtered(
                lambda partner: partner.customer_rank > 0 and not partner.parent_id
            )
        for company in companies:
            account = company.sng_default_receivable_account_id
            if not account:
                continue
            customer_partners.with_company(company).write({
                "property_account_receivable_id": account.id,
            })

    def _sng_assign_default_payable_accounts(self, companies=None):
        companies = companies or self.env.companies
        supplier_partners = self
        if not supplier_partners:
            supplier_partners = self.with_context(active_test=False).search([
                ("supplier_rank", ">", 0),
                ("parent_id", "=", False),
            ])
        else:
            supplier_partners = supplier_partners.filtered(
                lambda partner: partner.supplier_rank > 0 and not partner.parent_id
            )
        for company in companies:
            account = company.sng_default_payable_account_id
            if not account:
                continue
            supplier_partners.with_company(company).write({
                "property_account_payable_id": account.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._sng_assign_default_receivable_accounts()
        partners._sng_assign_default_payable_accounts()
        return partners

    def write(self, vals):
        result = super().write(vals)
        if "customer_rank" in vals:
            self._sng_assign_default_receivable_accounts()
        if "supplier_rank" in vals:
            self._sng_assign_default_payable_accounts()
        return result
