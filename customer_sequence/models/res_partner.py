# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Aysha Shalin (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC
#    LICENSE (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from odoo import api, fields, models


class ResPartner(models.Model):
    """ Inherited Partner for generating unique sequence """
    _inherit = 'res.partner'
    @api.model
    def _search_display_name(self, operator, value):
        """Override to also search by unique_id"""
        domain = super()._search_display_name(operator, value)
        if operator in ('ilike', 'like', '=', '=ilike'):
            domain = ['|', ('unique_id', operator, value)] + domain
        return domain

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if not args:
            args = []
        if name:
            # Prioritize unique_id match
             # We want to find partners where unique_id matches name (exact or partial)
            domain_code = [('unique_id', operator, name)] + args
            # Search strictly by code first
            partners_code = self.search(domain_code, limit=limit)
            
            # Use name_get() or display_name to format results
            # In Odoo 17+, name_get is deprecated, name_search returns list of (id, display_name)
            # But BaseModel.name_search implementation calls search_fetch and uses display_name
            # If we call super().name_search, it returns list of tuples.
            # So we should return list of tuples.
            
            res_code = [(p.id, p.display_name) for p in partners_code]
            
            # Standard search
            res_standard = super().name_search(name, args, operator, limit=limit)
            
            # Combine: Code matches first
            seen_ids = set(p[0] for p in res_code)
            final_res = res_code + [r for r in res_standard if r[0] not in seen_ids]
            
            return final_res[:limit]
            
        return super().name_search(name, args, operator, limit=limit)

    unique_id = fields.Char(
        string='Código cliente',
        help="The Unique Sequence no",
        default='/',
        copy=False,
        index=True,  # Index for better search performance
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Super create function for generating sequence.

        Only sets the ``unique_id`` field; no longer modifica el nombre del
        partner para evitar que el código aparezca varias veces en pantalla.
        """
        records = super(ResPartner, self).create(vals_list)
        company = self.env.company.sudo()
        for rec in records:
            if rec.unique_id == '/':
                code = company.next_code or company.customer_code
                rec.unique_id = code
                company.write({'next_code': code + 1})
        return records
