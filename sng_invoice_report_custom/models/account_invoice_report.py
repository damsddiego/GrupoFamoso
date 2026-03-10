# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools import SQL


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    partner_code_name = fields.Char(
        string='Cliente (Código - Nombre)',
        readonly=True,
        help='Código y nombre del cliente concatenados'
    )

    @api.model
    def _select(self) -> SQL:
        """
        Extiende el SELECT para incluir el código (unique_id) y nombre del
        cliente concatenados. El campo 'unique_id' es definido por el módulo
        customer_sequence en res.partner.
        """
        select_sql = super()._select()

        # Usar el campo unique_id del partner del move (cliente de la factura)
        additional_select = SQL(
            """
                ,CASE
                    WHEN move_partner.unique_id IS NOT NULL
                         AND move_partner.unique_id != '/'
                         AND move_partner.unique_id != ''
                    THEN move_partner.unique_id || ' - ' || move_partner.name
                    ELSE move_partner.name
                END AS partner_code_name
            """
        )

        return SQL('%s %s', select_sql, additional_select)

    @api.model
    def _from(self) -> SQL:
        """
        Extiende el FROM para añadir el JOIN con el partner del move,
        que es quien tiene el unique_id (código de cliente).
        """
        from_sql = super()._from()

        additional_from = SQL(
            """
                LEFT JOIN res_partner move_partner ON move_partner.id = move.partner_id
            """
        )

        return SQL('%s %s', from_sql, additional_from)
