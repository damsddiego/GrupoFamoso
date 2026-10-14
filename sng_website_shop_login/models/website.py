from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    sng_shop_login_required = fields.Boolean(
        string='Tienda solo para clientes registrados',
        help='Los visitantes sin sesión no ven productos: la tienda redirige al login '
             'y el catálogo queda oculto en búsquedas, snippets y sitemap.',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'sng_shop_login_required' in vals:
            # Las reglas de ir.rule cachean su dominio por usuario y website_id:
            # sin esto los workers seguirían aplicando el valor anterior.
            self.env.registry.clear_cache()
        return res
