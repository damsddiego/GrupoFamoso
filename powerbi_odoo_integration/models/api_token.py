from odoo import models, fields, api

class ApiToken(models.Model):
    _name = 'powerbi.api.token'
    _description = 'API Access Token'

    name = fields.Char('Token', copy=False)
    user_id = fields.Many2one('res.users', 'User', required=True)
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Token must be unique!'),
    ]


    @api.model
    def _generate_token(self):
        import secrets
        return secrets.token_urlsafe(32)

    def action_generate_token(self):
        for rec in self:
            rec.name = self._generate_token()



class PowerBIModel(models.Model):
    _name = 'powerbi.model'
    _description = 'Power BI Exposed Model'

    name = fields.Char('Display Name', required=True)
    model_id = fields.Many2one('ir.model', string='Odoo Model', required=True, ondelete='cascade')
    field_ids = fields.Many2many(
        'ir.model.fields',
        'powerbi_model_ir_model_fields_rel',
        'powerbi_model_id',
        'field_id',
        string='Odoo Fields',
        domain="[('model_id', '=', model_id)]"
    )
    active = fields.Boolean('Active', default=True)

class ApiAuditTrail(models.Model):
    _name = 'powerbi.api.audit'
    _description = 'API Audit Trail'

    name = fields.Char('API Endpoint', required=True)
    user_id = fields.Many2one('res.users', string='User')
    token_id = fields.Many2one('powerbi.api.token', string='API Token')
    called_at = fields.Datetime('Called At', default=fields.Datetime.now)
    request_info = fields.Text('Request Info')
    response_status = fields.Char('Status')