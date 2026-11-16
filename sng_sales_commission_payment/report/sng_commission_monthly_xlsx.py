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
        sheet.set_column(3, 9, 16)
        sheet.set_column(4, 4, 24)
        sheet.write(0, 0, 'Comisiones Mensuales', title)
        subtitle = (data or {}).get('subtitle')
        if subtitle:
            sheet.write(1, 0, subtitle)
        headers = ['Vendedor', 'Mes', 'Compañía', 'Base (sin IVA)', 'Tramo',
                   '% Comisión', 'Reversos', 'Comisión', 'Estado', 'Factura de Comisión']
        for col, text in enumerate(headers):
            sheet.write(2, col, text, header)
        sheet.freeze_panes(3, 0)
        row = 3
        for m in monthlies:
            sheet.write(row, 0, m.salesperson_id.name or '')
            sheet.write(row, 1, m.period_label or '')
            sheet.write(row, 2, m.company_id.name or '')
            sheet.write_number(row, 3, m.base_amount, money)
            sheet.write(row, 4, m.tier_id.name or '')
            sheet.write_number(row, 5, m.percentage, pct)
            sheet.write_number(row, 6, m.adjustment_amount or 0.0, money)
            sheet.write_number(row, 7, m.commission_amount, money)
            sheet.write(row, 8, state_labels.get(m.state, m.state))
            sheet.write(row, 9, m.bill_id.name or '')
            row += 1
        sheet.write(row, 2, 'TOTAL', bold)
        sheet.write_number(row, 3, sum(monthlies.mapped('base_amount')), money_bold)
        sheet.write_number(row, 6, sum(monthlies.mapped('adjustment_amount')), money_bold)
        sheet.write_number(row, 7, sum(monthlies.mapped('commission_amount')), money_bold)

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
        sheet.set_column(5, 5, 14)
        sheet.set_column(6, 10, 15)
        headers = ['Vendedor', 'Fecha Pago', 'Factura', 'Cliente', 'Pago',
                   'N° Recibo (app)', 'Monto Pago Aplicado', 'Tipo de Factura',
                   '% Impuesto Efectivo', 'Base de Comisión']
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
                sheet.write(row, 5, line.sng_numero_recibo or '')
                sheet.write_number(row, 6, line.payment_amount, money)
                sheet.write(row, 7, tax_labels.get(line.tax_profile, ''))
                sheet.write_number(row, 8, line.effective_tax_rate, pct)
                sheet.write_number(row, 9, line.commission_base, money)
                row += 1
        sheet.write(row, 5, 'TOTAL', bold)
        all_lines = monthlies.mapped('commission_line_ids')
        sheet.write_number(row, 6, sum(all_lines.mapped('payment_amount')), money_bold)
        sheet.write_number(row, 9, sum(all_lines.mapped('commission_base')), money_bold)

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

        if (data or {}).get('include_analysis', True):
            self._sng_write_analysis_sheets(workbook, monthlies, header, bold, money, money_bold, pct, date_fmt)

    def _sng_write_analysis_sheets(self, workbook, monthlies, header, bold, money, money_bold, pct, date_fmt):
        """Hojas del análisis de la comisión (ver sng_commission_monthly_analysis)."""

        def write_date(sheet, row, col, value):
            if value:
                sheet.write_datetime(row, col, value, date_fmt)

        # ---- Origen y cuadre ----
        sheet = workbook.add_worksheet('Origen y cuadre')
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 16)
        sheet.set_column(2, 2, 48)
        sheet.set_column(3, 3, 9)
        sheet.set_column(4, 5, 18)
        headers = ['Vendedor', 'Mes', 'Origen del pago', 'Pagos', 'Cobrado', 'Base (sin IVA)']
        for col, text in enumerate(headers):
            sheet.write(0, col, text, header)
        sheet.freeze_panes(1, 0)
        row = 1
        for m in monthlies:
            origin = m._sng_analysis_origin()
            name, period = m.salesperson_id.name or '', m.period_label or ''
            for group in origin['groups']:
                sheet.write_row(row, 0, [name, period, group['label'], group['payment_count']])
                sheet.write_number(row, 4, group['payment_amount'], money)
                sheet.write_number(row, 5, group['commission_base'], money)
                row += 1
            reversals = origin['reversals']
            if reversals['payment_count']:
                sheet.write_row(row, 0, [name, period, 'Reversos de meses cerrados', reversals['payment_count']])
                sheet.write_number(row, 4, reversals['payment_amount'], money)
                sheet.write_number(row, 5, 0.0, money)
                row += 1
            check = origin['check']
            for label, value, fmt in (
                ('Base (suma de los pagos)', check['base'], money),
                ('% del tramo', check['percentage'], pct),
                ('Base × %', check['gross'], money),
                ('Reversos', check['adjustment'], money),
                ('Comisión calculada', check['computed'], money_bold),
                ('Comisión del módulo', check['module'], money_bold),
                ('Diferencia', check['difference'], money),
            ):
                sheet.write_row(row, 0, [name, period])
                sheet.write(row, 2, label, bold)
                sheet.write_number(row, 5, value, fmt)
                row += 1
            row += 1

        # ---- Notas de crédito sobre facturas ya cobradas ----
        sheet = workbook.add_worksheet('Notas de crédito')
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 16)
        sheet.set_column(2, 4, 22)
        sheet.set_column(5, 5, 35)
        sheet.set_column(6, 7, 14)
        sheet.set_column(8, 13, 18)
        sheet.write(0, 0, 'Notas hechas el día del pago o después sobre facturas cobradas en el mes. La comisión es '
                          'sobre lo cobrado: una nota aplicada a facturas se compensa sola (esa parte no comisiona); '
                          'solo lo devuelto en efectivo al cliente es comisión pagada de más.')
        headers = ['Vendedor', 'Mes', 'Nota de crédito', 'Motivo', 'Factura', 'Cliente',
                   'Nota hecha', 'Pago confirmado', 'Monto nota', 'Aplicada a facturas', 'Sin aplicar',
                   'Devuelta en efectivo', 'Otro asiento', 'Comisión de más']
        for col, text in enumerate(headers):
            sheet.write(1, col, text, header)
        sheet.freeze_panes(2, 0)
        row = 2
        keys = ('total', 'to_invoices', 'unapplied', 'refunded', 'other', 'overpaid')
        totals = dict.fromkeys(keys, 0.0)
        for m in monthlies:
            result = m._sng_analysis_credit_notes()
            for item in result['rows']:
                sheet.write_row(row, 0, [m.salesperson_id.name or '', m.period_label or '', item['credit_note'] or '',
                                         item['reason'], item['invoice'] or '', item['partner'] or ''])
                write_date(sheet, row, 6, item['credit_note_date'])
                write_date(sheet, row, 7, item['confirmation_date'])
                for col, key in enumerate(keys, 8):
                    sheet.write_number(row, col, item[key], money)
                row += 1
            for key in keys:
                totals[key] += result[key]
        sheet.write(row, 7, 'TOTAL', bold)
        for col, key in enumerate(keys, 8):
            sheet.write_number(row, col, totals[key], money_bold)

        # ---- Cobros de meses anteriores ----
        sheet = workbook.add_worksheet('Cobros meses anteriores')
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 16)
        sheet.set_column(2, 3, 22)
        sheet.set_column(4, 4, 35)
        sheet.set_column(5, 5, 22)
        sheet.set_column(6, 7, 14)
        sheet.set_column(8, 8, 30)
        sheet.set_column(9, 12, 16)
        headers = ['Vendedor', 'Mes', 'Pago', 'Recibo', 'Cliente', 'Factura', 'Fecha pago', 'Confirmado',
                   'Motivo', 'Base', 'Comisión', '% mes original', 'Diferencia']
        for col, text in enumerate(headers):
            sheet.write(0, col, text, header)
        sheet.freeze_panes(1, 0)
        row = 1
        totals = [0.0, 0.0, 0.0]
        for m in monthlies:
            result = m._sng_analysis_prior_collections()
            for item in result['rows']:
                sheet.write_row(row, 0, [m.salesperson_id.name or '', m.period_label or '', item['payment'] or '',
                                         item['receipt'], item['partner'] or '', item['invoice'] or ''])
                write_date(sheet, row, 6, item['payment_date'])
                write_date(sheet, row, 7, item['confirmation_date'])
                sheet.write(row, 8, item['reason'])
                sheet.write_number(row, 9, item['commission_base'], money)
                sheet.write_number(row, 10, item['commission'], money)
                if item['original_percentage'] is None:
                    sheet.write(row, 11, 'sin mensual')
                else:
                    sheet.write_number(row, 11, item['original_percentage'], pct)
                sheet.write_number(row, 12, item['difference'], money)
                row += 1
            totals[0] += result['commission_base']
            totals[1] += result['commission']
            totals[2] += result['difference']
        sheet.write(row, 8, 'TOTAL', bold)
        sheet.write_number(row, 9, totals[0], money_bold)
        sheet.write_number(row, 10, totals[1], money_bold)
        sheet.write_number(row, 12, totals[2], money_bold)

        # ---- Reversos que no se devolvieron ----
        sheet = workbook.add_worksheet('Reversos sin devolver')
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 16)
        sheet.set_column(2, 3, 22)
        sheet.set_column(4, 4, 35)
        sheet.set_column(5, 5, 16)
        sheet.set_column(6, 7, 26)
        sheet.set_column(8, 9, 16)
        sheet.set_column(10, 10, 60)
        sheet.set_column(11, 12, 16)
        sheet.write(0, 0, 'Pagos desaplicados de un mes cerrado (se restó la comisión) y vueltos a aplicar sin generar '
                          'comisión nueva. "No devuelto" es la parte del reverso que corresponde a lo reaplicado y que '
                          'le toca a este vendedor.')
        headers = ['Vendedor', 'Mes', 'Pago', 'Recibo', 'Cliente', 'Mes original', 'Factura del reverso',
                   'Aplicado ahora a', 'Desaplicado', 'Reaplicado', 'Qué hacer', 'Se le restó', 'No devuelto']
        for col, text in enumerate(headers):
            sheet.write(1, col, text, header)
        sheet.freeze_panes(2, 0)
        row = 2
        total_reversed = total = 0.0
        for m in monthlies:
            result = m._sng_analysis_unreturned_reversals()
            for item in result['rows']:
                sheet.write_row(row, 0, [m.salesperson_id.name or '', m.period_label or '', item['payment'] or '',
                                         item['receipt'], item['partner'] or '', item['original_period'],
                                         item['reversed_invoice'] or '', item['new_invoices']])
                sheet.write_number(row, 8, item['unapplied_amount'], money)
                sheet.write_number(row, 9, item['reapplied_amount'], money)
                sheet.write(row, 10, item['action'])
                sheet.write_number(row, 11, item['reversed_amount'], money)
                sheet.write_number(row, 12, item['amount'], money)
                row += 1
            total_reversed += result['reversed_amount']
            total += result['amount']
        sheet.write(row, 10, 'TOTAL', bold)
        sheet.write_number(row, 11, total_reversed, money_bold)
        sheet.write_number(row, 12, total, money_bold)
