# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models

def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import ValidationError
    version_info = common.exp_version()
    server_version = version_info.get('server_version', '')
    if not server_version.startswith('18.'):
        raise ValidationError(
            'This module supports Odoo 18.x series. Your Odoo version is {}.'.format(server_version)
        )
    return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
