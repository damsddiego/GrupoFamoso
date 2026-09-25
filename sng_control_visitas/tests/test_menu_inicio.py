# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install', 'sng_control_visitas')
class TestMenuInicio(TransactionCase):
    """La app Ruteros abre una pantalla distinta según el grupo."""

    def _inicio(self, login, groups):
        user = new_test_user(self.env, login=login, groups=groups)
        accion = self.env.ref('sng_control_visitas.action_sng_ruteros_inicio')
        return accion.with_user(user).run()['id']

    def test_menu_raiz_usa_accion_de_inicio(self):
        menu = self.env.ref('sng_ruteros_pagos.menu_ruteros_root')
        self.assertEqual(
            menu.action,
            self.env.ref('sng_control_visitas.action_sng_ruteros_inicio'))

    def test_gerencia_abre_matriz(self):
        self.assertEqual(
            self._inicio('rut_gerencia', 'base.group_user,'
                         'sng_control_visitas.group_control_visitas_manager'),
            self.env.ref(
                'sng_control_visitas.action_sng_control_visitas_linea').id)

    def test_televentas_abre_seguimiento(self):
        self.assertEqual(
            self._inicio('rut_televentas', 'base.group_user,'
                         'sng_control_visitas.group_control_visitas_user,'
                         'account.group_account_invoice'),
            self.env.ref(
                'sng_control_visitas.action_sng_televentas_seguimiento').id)

    def test_contabilidad_sigue_en_recibos(self):
        self.assertEqual(
            self._inicio('rut_caja', 'base.group_user,account.group_account_invoice'),
            self.env.ref('sng_ruteros_pagos.action_ruteros_recibos').id)
