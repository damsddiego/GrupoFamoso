import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    invoices = env["account.move"].search([
        ("move_type", "in", ("out_invoice", "out_refund")),
        "|",
        ("state_tributacion", "=", "rechazado"),
        ("einvoice_had_rejection", "=", True),
    ])
    if invoices:
        _logger.info(
            "sng_rejected_invoice_tracker: Computing fe_rejection_detail for %d existing rejected invoices",
            len(invoices),
        )
        invoices._compute_fe_rejection_detail()
