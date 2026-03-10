from odoo import models
from odoo.exceptions import AccessDenied

class ResUsers(models.Model):
    _inherit = 'res.users'
    
    # Disable login for users who are restricted from login
    def _check_credentials(self, credential, env):
        """ Extends authentication check by verifying if the user is restricted from login. """
        user_id = self.env.user.id
        
        access_records = self.env['sh.access.manager'].sudo().search([
            ('responsible_user_ids', 'in', [user_id]),('active_rule', '=', True),('company_id', '=', self.env.company.id)
        ])

        if any(access_records.mapped('sh_disable_user_login')):
            raise AccessDenied("Your login has been temporarily Restricted. Please contact the Administrator for further assistance.")

        return super(ResUsers, self)._check_credentials(credential, env)
