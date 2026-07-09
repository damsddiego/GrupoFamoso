from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def _get_auto_discount_company(self, vals=None):
        if vals:
            company_id = vals.get('company_id')
            if company_id:
                return self.env['res.company'].browse(company_id)

            move_id = vals.get('move_id')
            if move_id:
                return self.env['account.move'].browse(move_id).company_id

        return self.env.company

    @api.model
    def _get_auto_discount_config(self, company):
        company = company or self.env.company
        return {
            'enabled': company.enable_auto_discount_fields,
            'discount_code_id': company.auto_discount_code_id.id,
            'discount_note': company.auto_discount_note,
        }

    @api.model
    def _apply_auto_discount_values(self, vals, company):
        prepared_vals = dict(vals)
        config = self._get_auto_discount_config(company)

        if 'discount' not in prepared_vals or not config['enabled']:
            return prepared_vals

        if prepared_vals['discount'] and prepared_vals['discount'] > 0:
            if not prepared_vals.get('discount_code_id') and config['discount_code_id']:
                prepared_vals['discount_code_id'] = config['discount_code_id']
            if not prepared_vals.get('discount_note') and config['discount_note']:
                prepared_vals['discount_note'] = config['discount_note']
        else:
            if 'discount_code_id' not in prepared_vals:
                prepared_vals['discount_code_id'] = False
            if 'discount_note' not in prepared_vals:
                prepared_vals['discount_note'] = False

        return prepared_vals

    @api.onchange('discount')
    def _onchange_discount_auto_fill(self):
        """Automatically fill discount_code_id and discount_note when discount is applied"""
        for line in self:
            company = line.company_id or line.move_id.company_id or self.env.company
            config = line._get_auto_discount_config(company)

            if not config['enabled']:
                continue

            if line.discount and line.discount > 0:
                if config['discount_code_id']:
                    line.discount_code_id = config['discount_code_id']
                if config['discount_note']:
                    line.discount_note = config['discount_note']
            else:
                line.discount_code_id = False
                line.discount_note = False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-fill discount fields"""
        prepared_vals_list = []
        for vals in vals_list:
            company = self._get_auto_discount_company(vals)
            prepared_vals_list.append(
                self._apply_auto_discount_values(vals, company)
            )
        return super().create(prepared_vals_list)

    def write(self, vals):
        """Override write to auto-fill discount fields"""
        if 'discount' not in vals:
            return super().write(vals)

        result = True
        companies = self.mapped('company_id')
        if not companies:
            companies = self.env.company

        for company in companies:
            company_lines = self.filtered(lambda line: line.company_id == company)
            company_vals = self._apply_auto_discount_values(vals, company)
            result = super(AccountMoveLine, company_lines).write(company_vals) and result

        return result
