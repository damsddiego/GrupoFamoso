from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_auto_discount_config(self):
        """Get the discount configuration from settings"""
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'enabled': ICP.get_param('sng_auto_discount_fields.enable_auto_discount_fields', 'True') == 'True',
            'discount_code_id': int(ICP.get_param('sng_auto_discount_fields.auto_discount_code_id', 0) or 0),
            'discount_note': ICP.get_param('sng_auto_discount_fields.auto_discount_note', 'Promo'),
        }

    @api.onchange('discount')
    def _onchange_discount_auto_fill(self):
        """Automatically fill discount_code_id and discount_note when discount is applied"""
        config = self._get_auto_discount_config()

        if not config['enabled']:
            return

        if self.discount and self.discount > 0:
            # Use configured discount code
            if config['discount_code_id']:
                self.discount_code_id = config['discount_code_id']
            # Use configured discount note
            if config['discount_note']:
                self.discount_note = config['discount_note']
        else:
            # Clear the fields if no discount
            self.discount_code_id = False
            self.discount_note = False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-fill discount fields"""
        config = self._get_auto_discount_config()

        if config['enabled']:
            for vals in vals_list:
                if vals.get('discount') and vals['discount'] > 0:
                    # Use configured discount code if not already set
                    if not vals.get('discount_code_id') and config['discount_code_id']:
                        vals['discount_code_id'] = config['discount_code_id']
                    # Set configured discount note if not already set
                    if not vals.get('discount_note') and config['discount_note']:
                        vals['discount_note'] = config['discount_note']
        return super().create(vals_list)

    def write(self, vals):
        """Override write to auto-fill discount fields"""
        config = self._get_auto_discount_config()

        # If discount is being updated
        if 'discount' in vals and config['enabled']:
            if vals['discount'] and vals['discount'] > 0:
                # Only set if not explicitly provided
                if 'discount_code_id' not in vals and config['discount_code_id']:
                    vals['discount_code_id'] = config['discount_code_id']
                if 'discount_note' not in vals and config['discount_note']:
                    vals['discount_note'] = config['discount_note']
            else:
                # Clear fields if discount is removed
                if 'discount_code_id' not in vals:
                    vals['discount_code_id'] = False
                if 'discount_note' not in vals:
                    vals['discount_note'] = False
        return super().write(vals)
