from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sng_default_receivable_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta por cobrar clientes",
        domain=[
            ("account_type", "=", "asset_receivable"),
            ("deprecated", "=", False),
        ],
        check_company=True,
        help=(
            "Cuenta por cobrar que se asigna automaticamente a los clientes "
            "creados para esta compania."
        ),
    )

    sng_default_payable_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta por pagar proveedores",
        domain=[
            ("account_type", "=", "liability_payable"),
            ("deprecated", "=", False),
        ],
        check_company=True,
        help=(
            "Cuenta por pagar que se asigna automaticamente a los proveedores "
            "creados para esta compania."
        ),
    )
