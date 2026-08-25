# -*- coding: utf-8 -*-

from odoo import models


class CommissionMonthlyXlsx(models.AbstractModel):
    _name = 'report.sng_sales_commission_payment.commission_monthly_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Comisión Mensual (Excel)'

    def generate_xlsx_report(self, workbook, data, monthlies):
        Line = self.env['sng.commission.payment.line']
        tax_labels = dict(Line._fields['tax_profile']._description_selection(self.env))
        state_labels = dict(monthlies._fields['state']._description_selection(self.env))

        title = workbook.add_format({'bold': True, 'font_size': 14})
        header = workbook.add_format({
            'bold': True, 'bg_color': '#D9D9D9', 'border': 1,
            'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
        })
        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})
        money_bold = workbook.add_format({'num_format': '#,##0.00', 'bold': True})
        pct = workbook.add_format({'num_format': '0.00'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'})

        # ---- Hoja Resumen: una fila por comisión mensual ----
        sheet = workbook.add_worksheet('Resumen')
        sheet.set_column(0, 0, 35)
        sheet.set_column(1, 2, 18)
        sheet.set_column(3, 8, 16)
        sheet.write(0, 0, 'Comisiones Mensuales', title)
        headers = ['Vendedor', 'Mes', 'Compañía', 'Base (sin IVA)',
                   '% Comisión', 'Reversos', 'Comisión', 'Estado', 'Factura de Comisión']
        for col, text in enumerate(headers):
            sheet.write(2, col, text, header)
        row = 3
        for m in monthlies:
            sheet.write(row, 0, m.salesperson_id.name or '')
            sheet.write(row, 1, m.period_label or '')
            sheet.write(row, 2, m.company_id.name or '')
            sheet.write_number(row, 3, m.base_amount, money)
            sheet.write_number(row, 4, m.percentage, pct)
            sheet.write_number(row, 5, m.adjustment_amount or 0.0, money)
            sheet.write_number(row, 6, m.commission_amount, money)
            sheet.write(row, 7, state_labels.get(m.state, m.state))
            sheet.write(row, 8, m.bill_id.name or '')
            row += 1
        sheet.write(row, 2, 'TOTAL', bold)
        sheet.write_number(row, 3, sum(monthlies.mapped('base_amount')), money_bold)
        sheet.write_number(row, 5, sum(monthlies.mapped('adjustment_amount')), money_bold)
        sheet.write_number(row, 6, sum(monthlies.mapped('commission_amount')), money_bold)

        # ---- Hoja Análisis: resumen por tipo de factura ----
        sheet = workbook.add_worksheet('Análisis IVA')
        sheet.set_column(0, 1, 35)
        sheet.set_column(2, 4, 18)
        headers = ['Vendedor / Mes', 'Tipo de Factura', 'Líneas',
                   'Pagado (con IVA)', 'Base (sin IVA)']
        for col, text in enumerate(headers):
            sheet.write(0, col, text, header)
        row = 1
        for m in monthlies:
            for item in m._get_tax_profile_summary():
                sheet.write(row, 0, '%s - %s' % (m.salesperson_id.name or '', m.period_label or ''))
                sheet.write(row, 1, item['label'])
                sheet.write_number(row, 2, item['count'])
                sheet.write_number(row, 3, item['payment_amount'], money)
                sheet.write_number(row, 4, item['commission_base'], money)
                row += 1

        # ---- Hoja Detalle: todas las líneas de pago ----
        sheet = workbook.add_worksheet('Detalle')
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 4, 22)
        sheet.set_column(3, 3, 35)
        sheet.set_column(5, 9, 15)
        headers = ['Vendedor', 'Fecha Pago', 'Factura', 'Cliente', 'Pago',
                   'Monto Pago Aplicado', 'Tipo de Factura', '% Impuesto Efectivo',
                   'Base de Comisión']
        for col, text in enumerate(headers):
            sheet.write(0, col, text, header)
        row = 1
        for m in monthlies:
            for line in m.commission_line_ids:
                sheet.write(row, 0, m.salesperson_id.name or '')
                if line.payment_date:
                    sheet.write_datetime(row, 1, line.payment_date, date_fmt)
                sheet.write(row, 2, line.invoice_id.name or '')
                sheet.write(row, 3, line.partner_id.name or '')
                sheet.write(row, 4, line.payment_id.name or '')
                sheet.write_number(row, 5, line.payment_amount, money)
                sheet.write(row, 6, tax_labels.get(line.tax_profile, ''))
                sheet.write_number(row, 7, line.effective_tax_rate, pct)
                sheet.write_number(row, 8, line.commission_base, money)
                row += 1
        sheet.write(row, 4, 'TOTAL', bold)
        all_lines = monthlies.mapped('commission_line_ids')
        sheet.write_number(row, 5, sum(all_lines.mapped('payment_amount')), money_bold)
        sheet.write_number(row, 8, sum(all_lines.mapped('commission_base')), money_bold)

        # ---- Hoja Reversos: comisiones pagadas de pagos cancelados ----
        reversals = monthlies.mapped('reversal_line_ids')
        if reversals:
            reason_labels = dict(
                reversals._fields['reversal_reason']._description_selection(reversals.env))
            sheet = workbook.add_worksheet('Reversos')
            sheet.set_column(0, 0, 30)
            sheet.set_column(1, 4, 22)
            sheet.set_column(3, 3, 35)
            sheet.set_column(5, 7, 18)
            headers = ['Vendedor', 'Mes del Descuento', 'Pago', 'Cliente', 'Factura',
                       'Motivo', 'Mes Original', 'Descuento']
            for col, text in enumerate(headers):
                sheet.write(0, col, text, header)
            row = 1
            for line in reversals:
                sheet.write(row, 0, line.salesperson_id.name or '')
                sheet.write(row, 1, line.monthly_id.period_label or '')
                sheet.write(row, 2, line.payment_id.name or '')
                sheet.write(row, 3, line.partner_id.name or '')
                sheet.write(row, 4, line.invoice_id.name or '')
                sheet.write(row, 5, reason_labels.get(line.reversal_reason, ''))
                sheet.write(row, 6, line.original_monthly_id.period_label or '')
                sheet.write_number(row, 7, line.commission_adjustment, money)
                row += 1
            sheet.write(row, 6, 'TOTAL', bold)
            sheet.write_number(row, 7, sum(reversals.mapped('commission_adjustment')), money_bold)
