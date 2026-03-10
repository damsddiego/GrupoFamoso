from odoo import api, models


class InvoiceSalespersonReport(models.AbstractModel):
    _name = 'report.sng_invoice_report.report_invoice_salesperson_document'
    _description = 'Invoice Report by Salesperson'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get report values for the PDF template."""
        docs = self.env['invoice.report.wizard'].browse(docids)

        # Use data passed from the wizard action, not recalculate
        report_data = data if data else {}

        # Remove company from data dict if present - it will be accessed via context
        if 'company' in report_data:
            del report_data['company']

        return {
            'doc_ids': docids,
            'doc_model': 'invoice.report.wizard',
            'docs': docs,
            'data': report_data,
            'company': self.env.company,
        }
