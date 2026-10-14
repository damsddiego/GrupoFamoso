import re
from urllib.parse import quote

import werkzeug.exceptions

from odoo import models
from odoo.http import request

# /shop y todo lo que cuelga de él, con prefijo de idioma opcional (/es_CR/shop/...)
SHOP_PATH = re.compile(r'^(/[a-z]{2}(_[A-Za-z0-9@]+)?)?/shop(/|$)')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, arguments):
        # Antes que super(): los argumentos del route (p. ej. el producto) ya
        # vienen filtrados por la regla y super() respondería 403/404.
        if cls._sng_shop_login_redirect(rule):
            werkzeug.exceptions.abort(request.redirect(cls._sng_login_url(), code=303))
        super()._pre_dispatch(rule, arguments)

    @classmethod
    def _sng_shop_login_redirect(cls, rule):
        routing = rule.endpoint.routing
        if not routing.get('website') or routing.get('type') != 'http':
            return False
        if not SHOP_PATH.match(request.httprequest.path):
            return False
        # Corre antes de super(): request.website aún no está asignado y el
        # contexto puede traer el idioma del navegador (p. ej. es_ES) sin
        # instalar, que revienta al leer campos. Igual que website._match().
        website = request.env['website'].with_context(lang=None).get_current_website()
        if not website.sng_shop_login_required:
            return False
        return request.env.user.with_context(lang=None)._is_public()

    @classmethod
    def _sng_login_url(cls):
        path = request.httprequest.full_path.rstrip('?')
        return '/web/login?redirect=%s' % quote(path, safe='')
