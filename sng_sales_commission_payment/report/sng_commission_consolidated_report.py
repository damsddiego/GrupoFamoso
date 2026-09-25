# -*- coding: utf-8 -*-

from odoo import api, models


class ReportCommissionConsolidated(models.AbstractModel):
    _name = 'report.sng_sales_commission_payment.consolidated_report'
    _description = 'Reporte Consolidado de Comisiones (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        if not docids:
            # Con `data` no vacío el cliente web no manda los ids en la URL:
            # llegan solo por el contexto de la acción.
            docids = (
                data.get('context', {}).get('active_ids')
                or self.env.context.get('active_ids')
                or []
            )
        wizards = self.env['sng.commission.report.wiz'].browse(docids)
        wizard = wizards[:1]
        monthlies = wizard._get_monthlies() if wizard else self.env['sng.commission.monthly']
        return {
            'doc_ids': wizards.ids,
            'doc_model': 'sng.commission.report.wiz',
            'docs': wizards,
            'wizard': wizard,
            'monthlies': monthlies,
            'totals': wizard._get_totals(monthlies) if wizard else {},
            'data': data,
        }


class CommissionConsolidatedXlsx(models.AbstractModel):
    _name = 'report.sng_sales_commission_payment.consolidated_xlsx'
    _inherit = 'report.sng_sales_commission_payment.commission_monthly_xlsx'
    _description = 'Reporte Consolidado de Comisiones (Excel)'

    def generate_xlsx_report(self, workbook, data, wizards):
        wizard = wizards[:1]
        monthlies = wizard._get_monthlies() if wizard else self.env['sng.commission.monthly']
        data = dict(data or {}, subtitle=wizard._get_subtitle() if wizard else '')
        return super().generate_xlsx_report(workbook, data, monthlies)
