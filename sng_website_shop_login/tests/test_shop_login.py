from urllib.parse import urlparse

from odoo.tests import HttpCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestShopLogin(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Sitio propio que gana por dominio sobre los existentes
        host = urlparse(cls.base_url()).hostname
        cls.website = cls.env['website'].create({
            'name': 'Tienda privada test',
            'domain': 'http://%s' % host,
            'company_id': cls.env.company.id,
            'sng_shop_login_required': True,
        })
        # Mismo idioma único que el sitio real, para que /shop no redirija a /<lang>/shop
        lang = cls.env['res.lang']._activate_lang('es_CR')
        cls.website.write({'language_ids': [(6, 0, lang.ids)], 'default_lang_id': lang.id})
        cls.product = cls.env['product.template'].create({
            'name': 'Casco SNG Prueba Privada',
            'list_price': 100,
            'sale_ok': True,
            'is_published': True,
            'website_id': cls.website.id,
        })
        cls.portal = new_test_user(cls.env, login='sng_portal_shop', password='sng_portal_shop',
                                   groups='base.group_portal')

    def _get(self, path):
        return self.url_open(path, allow_redirects=False)

    def _final(self, path):
        """Sigue redirecciones (slug canónico, idioma) y devuelve la respuesta final."""
        return self.url_open(path)

    def _autocomplete(self):
        res = self.make_jsonrpc_request('/website/snippet/autocomplete', {
            'search_type': 'products', 'term': 'Privada', 'order': 'name asc',
            'limit': 5, 'max_nb_chars': 100,
            'options': {'displayImage': False, 'displayDescription': False, 'displayExtraLink': False,
                        'displayDetail': False, 'allowFuzzy': False},
        })
        return ' '.join(str(r.get('name')) for r in res.get('results', []))

    def test_public_redirected_to_login(self):
        for path in ('/shop', '/shop/%s' % self.product.id, '/shop/compare', '/shop/wishlist'):
            res = self._get(path)
            self.assertIn(res.status_code, (302, 303), path)
            self.assertIn('/web/login?redirect=', res.headers['Location'], path)

    def test_login_page_notice(self):
        res = self._final('/web/login')
        self.assertEqual(res.status_code, 200)
        self.assertIn('es exclusivo para clientes', res.text)

    def test_public_search_hides_products(self):
        self.assertNotIn('Casco SNG Prueba', self._autocomplete())

    def test_portal_user_sees_shop(self):
        self.authenticate('sng_portal_shop', 'sng_portal_shop')
        res = self._final('/shop/%s' % self.product.id)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('/web/login', res.url)
        self.assertIn(self.product.name, res.text)
        self.assertIn('Casco SNG Prueba', self._autocomplete())

    def test_flag_off_public_sees_shop(self):
        self.website.sng_shop_login_required = False
        res = self._final('/shop/%s' % self.product.id)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('/web/login', res.url)
        self.assertIn(self.product.name, res.text)
        self.assertIn('Casco SNG Prueba', self._autocomplete())

    def test_backend_not_affected(self):
        # Sin request de sitio web la regla no filtra (backend, crons, scripts)
        self.assertTrue(self.env['product.template'].with_user(self.env.ref('base.public_user'))
                        .search([('id', '=', self.product.id)]))

    def test_toggle_takes_effect_immediately(self):
        self.assertNotIn('Casco SNG Prueba', self._autocomplete())
        self.website.sng_shop_login_required = False
        self.assertIn('Casco SNG Prueba', self._autocomplete())
        self.website.sng_shop_login_required = True
        self.assertNotIn('Casco SNG Prueba', self._autocomplete())

    def test_browser_lang_not_installed(self):
        # Navegador en es-ES (no instalado): no debe dar 400 "Invalid language code"
        headers = {'Accept-Language': 'es-ES,es;q=0.9'}
        res = self.url_open('/', headers=headers, allow_redirects=False)
        self.assertNotEqual(res.status_code, 400)
        self.assertNotEqual(res.status_code, 500)
        res = self.url_open('/shop', headers=headers, allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertIn('/web/login?redirect=', res.headers['Location'])
