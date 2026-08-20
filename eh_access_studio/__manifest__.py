# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'post_init_hook': 'post_init_hook',
    "name": "User Access Studio",
    "summary": (
        "User-driven access overlay for Odoo 18. Hide menus, fields, "
        "buttons, tabs, filters and chatter. Per-model record rules with "
        "smart placeholders. Audit log of every blocked operation."
    ),
    "version": "18.0.1.0.0",
    "author": "ERP Heritage",
    "website": "https://www.erpheritage.com.au/",
    "license": "LGPL-3",
    "category": "Productivity/Tools",
    "depends": [
        "base",
        "mail",
        "web",
    ],
    "data": [
        "security/eh_access_studio_groups.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "wizards/eh_access_yaml_wizard_views.xml",
        "wizards/eh_access_template_wizard_views.xml",
        "views/eh_access_profile_views.xml",
        "views/res_users_views.xml",
        "views/eh_access_studio_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "eh_access_studio/static/src/js/chatter_patch.js",
            "eh_access_studio/static/src/xml/chatter_patch.xml",
        ],
    },
    "images": ["static/description/banner.png"],
    "application": True,
    "installable": True,
    "auto_install": False,
}
