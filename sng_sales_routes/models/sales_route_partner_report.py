# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class SngSalesRoutePartnerReport(models.Model):
    _name = "sng.sales.route.partner.report"
    _description = "Reporte de Clientes por Ruta/Territorio"
    _auto = False
    _rec_name = "name"
    _order = "route_code, name"

    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    unique_id = fields.Char(string="Unique ID", readonly=True)
    name = fields.Char(string="Nombre", readonly=True)
    commercial_name = fields.Char(string="Nombre Comercial", readonly=True)
    route_code = fields.Char(string="Código de ruta", readonly=True)
    sales_route_id = fields.Many2one(
        "sng.sales.route",
        string="Ruta",
        readonly=True,
    )
    route_name = fields.Char(string="Ruta (Nombre)", readonly=True)
    salesperson_id = fields.Many2one(
        "res.partner",
        string="Vendedor",
        readonly=True,
    )
    salesperson_name = fields.Char(string="Nombre vendedor", readonly=True)
    phone = fields.Char(string="Teléfono", readonly=True)
    payment_term_name = fields.Char(string="Términos de pago", readonly=True)
    pricelist_name = fields.Char(string="Lista de precio", readonly=True)
    last_invoice_date = fields.Date(string="Fecha última factura", readonly=True)
    address = fields.Char(string="Dirección", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)

    def init(self):
        self.env.cr.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'res_partner'
                AND column_name = 'assigned_salesperson_id'
            """
        )
        row = self.env.cr.fetchone()
        salesperson_is_jsonb = row and row[0] == "jsonb"
        if salesperson_is_jsonb:
            salesperson_select = "salesperson_prop.id AS salesperson_id"
            salesperson_join = """
                LEFT JOIN LATERAL (
                    SELECT NULLIF(value, '')::integer AS id
                    FROM jsonb_each_text(rp.assigned_salesperson_id)
                    ORDER BY CASE
                        WHEN key = COALESCE(rp.company_id::text, '1') THEN 0
                        ELSE 1
                    END, key
                    LIMIT 1
                ) salesperson_prop ON TRUE
                LEFT JOIN res_partner salesperson ON salesperson.id = salesperson_prop.id
            """
            salesperson_groupby = "salesperson_prop.id"
        else:
            salesperson_select = "rp.assigned_salesperson_id AS salesperson_id"
            salesperson_join = """
                LEFT JOIN res_partner salesperson
                    ON salesperson.id = rp.assigned_salesperson_id
            """
            salesperson_groupby = "rp.assigned_salesperson_id"

        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    rp.id AS id,
                    rp.id AS partner_id,
                    rp.unique_id AS unique_id,
                    rp.name AS name,
                    rp.commercial_name AS commercial_name,
                    rp.sales_route_id AS sales_route_id,
                    route.code AS route_code,
                    COALESCE(route.name->>'es_CR', route.name->>'en_US', route_name.value) AS route_name,
                    %s,
                    salesperson.name AS salesperson_name,
                    COALESCE(rp.phone, rp.mobile, '') AS phone,
                    COALESCE(term.name->>'es_CR', term.name->>'en_US', term_name.value) AS payment_term_name,
                    COALESCE(pricelist.name->>'es_CR', pricelist.name->>'en_US', pricelist_name.value) AS pricelist_name,
                    CONCAT_WS(
                        ', ',
                        NULLIF(rp.street, ''),
                        NULLIF(rp.street2, ''),
                        NULLIF(rp.city, ''),
                        NULLIF(state.name, ''),
                        NULLIF(COALESCE(country.name->>'es_CR', country.name->>'en_US', country_name.value), '')
                    ) AS address,
                    rp.company_id AS company_id,
                    MAX(am.invoice_date) AS last_invoice_date
                FROM res_partner rp
                LEFT JOIN sng_sales_route route ON route.id = rp.sales_route_id
                LEFT JOIN LATERAL (
                    SELECT value
                    FROM jsonb_each_text(route.name)
                    LIMIT 1
                ) route_name ON TRUE
                %s
                LEFT JOIN LATERAL (
                    SELECT value::integer AS id
                    FROM jsonb_each_text(rp.property_payment_term_id)
                    ORDER BY CASE WHEN key = COALESCE(rp.company_id::text, '1') THEN 0 ELSE 1 END, key
                    LIMIT 1
                ) payment_prop ON TRUE
                LEFT JOIN account_payment_term term ON term.id = payment_prop.id
                LEFT JOIN LATERAL (
                    SELECT value
                    FROM jsonb_each_text(term.name)
                    LIMIT 1
                ) term_name ON TRUE
                LEFT JOIN LATERAL (
                    SELECT value::integer AS id
                    FROM jsonb_each_text(rp.specific_property_product_pricelist)
                    ORDER BY CASE WHEN key = COALESCE(rp.company_id::text, '1') THEN 0 ELSE 1 END, key
                    LIMIT 1
                ) pricelist_prop ON TRUE
                LEFT JOIN product_pricelist pricelist ON pricelist.id = pricelist_prop.id
                LEFT JOIN LATERAL (
                    SELECT value
                    FROM jsonb_each_text(pricelist.name)
                    LIMIT 1
                ) pricelist_name ON TRUE
                LEFT JOIN res_country_state state ON state.id = rp.state_id
                LEFT JOIN res_country country ON country.id = rp.country_id
                LEFT JOIN LATERAL (
                    SELECT value
                    FROM jsonb_each_text(country.name)
                    LIMIT 1
                ) country_name ON TRUE
                LEFT JOIN account_move am
                    ON am.commercial_partner_id = rp.id
                    AND am.move_type = 'out_invoice'
                    AND am.state = 'posted'
                    AND am.invoice_date IS NOT NULL
                WHERE rp.customer_rank > 0
                    AND rp.supplier_rank = 0
                    AND rp.active IS TRUE
                    AND rp.type = 'contact'
                    AND rp.is_salesperson IS NOT TRUE
                    AND NOT EXISTS (
                        SELECT 1 FROM res_users ru WHERE ru.partner_id = rp.id
                    )
                GROUP BY
                    rp.id,
                    rp.unique_id,
                    rp.name,
                    rp.commercial_name,
                    rp.sales_route_id,
                    route.code,
                    route.name,
                    route_name.value,
                    %s,
                    salesperson.name,
                    rp.phone,
                    rp.mobile,
                    term.name,
                    term_name.value,
                    pricelist.name,
                    pricelist_name.value,
                    rp.street,
                    rp.street2,
                    rp.city,
                    state.name,
                    country.name,
                    country_name.value,
                    rp.company_id
            )
            """
            % (
                self._table,
                salesperson_select,
                salesperson_join,
                salesperson_groupby,
            )
        )
