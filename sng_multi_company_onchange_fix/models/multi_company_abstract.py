# -*- coding: utf-8 -*-
"""Corrige el cálculo de ``company_id`` de OCA ``base_multi_company`` para
registros virtuales (onchange).

Síntoma en producción: al agregar un contacto hijo desde la pestaña
"Contactos y direcciones" de un cliente con varias compañías, el cliente web
de Odoo 18 manda el padre al ``onchange`` del hijo como un diccionario
(``parent_id: {'id': 11747, ...}``). El servidor lo convierte en un registro
virtual (NewId) y, en un registro virtual, ``record.company_ids`` devuelve
compañías también virtuales. La intersección ``env.companies & company_ids``
queda vacía y OCA cae al último recurso ``company_ids[:1]``: la primera
compañía del padre, que no tiene por qué ser la activa. El hijo se crea en esa
compañía y el usuario ya no puede leerlo ("res.partner company").

La corrección compara siempre contra los registros reales (``_origin``).
"""
from odoo import api, models


class MultiCompanyAbstract(models.AbstractModel):
    _inherit = "multi.company.abstract"

    @api.depends("company_ids")
    @api.depends_context("companies", "company", "_check_company_source_id")
    def _compute_company_id(self):
        for record in self:
            # ``_origin`` devuelve los registros reales aunque ``record`` sea
            # virtual; para registros reales es el mismo recordset.
            companies = record.company_ids._origin
            company_id = self.env.context.get(
                "_check_company_source_id"
            ) or self.env.context.get("force_company")
            if company_id in companies.ids:
                record.company_id = company_id
            else:
                common_companies = self.env.companies & companies
                if common_companies and (self.env.company in common_companies):
                    record.company_id = self.env.company.id
                elif common_companies:
                    record.company_id = common_companies[0].id
                else:
                    record.company_id = companies[:1].id
