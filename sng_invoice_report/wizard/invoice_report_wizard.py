import base64
import io
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class InvoiceReportWizard(models.TransientModel):
    _name = 'invoice.report.wizard'
    _description = 'Invoice Report by Salesperson Wizard'

    date_from = fields.Date(
        string='Date From',
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='Date To',
        required=True,
        default=fields.Date.context_today,
    )
    company_ids = fields.Many2many(
        'res.company',
        'invoice_report_wizard_company_rel',
        'wizard_id',
        'company_id',
        string='Companies',
        default=lambda self: self.env.companies.ids,
        help="Select companies to include in the report. Limited to your allowed companies.",
    )
    salesperson_ids = fields.Many2many(
        'res.partner',
        'invoice_report_wizard_salesperson_rel',
        'wizard_id',
        'partner_id',
        string='Salespersons',
        domain="[('is_salesperson', '=', True)]",
        help="Leave empty to include all salespersons",
    )
    invoice_type = fields.Selection([
        ('out_invoice', 'Customer Invoices'),
        ('out_refund', 'Customer Credit Notes'),
        ('all', 'All Customer Documents'),
    ], string='Invoice Type', default='out_invoice', required=True)

    payment_status = fields.Selection([
        ('all', 'All'),
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
    ], string='Payment Status', default='all', required=True)

    # Fields for Excel download
    excel_file = fields.Binary('Excel File', readonly=True)
    excel_filename = fields.Char('Excel Filename', readonly=True)

    @api.model
    def default_get(self, fields_list):
        """Set default companies to user's allowed companies."""
        res = super().default_get(fields_list)
        if 'company_ids' in fields_list and not res.get('company_ids'):
            res['company_ids'] = self.env.companies.ids
        return res

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise UserError(_("'Date From' must be earlier than 'Date To'."))

    def _get_invoices_domain(self):
        """Build the domain for filtering invoices.

        Respects multi-company access rules by filtering on company_ids.
        Only returns invoices from companies the user has access to.
        """
        allowed_companies = self._get_selected_companies()
        domain = [
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('state', '=', 'posted'),
        ]

        # Multi-company filter: only show invoices from selected companies
        # that are within user's allowed companies
        if allowed_companies:
            domain.append(('company_id', 'in', allowed_companies.ids))
        else:
            domain.append(('id', '=', False))

        domain.append(('move_type', 'in', self._get_report_move_types()))

        if self.salesperson_ids:
            domain.append(('salesperson_id', 'in', self.salesperson_ids.ids))
        # Note: When no salesperson selected, we don't add any filter here.
        # Invoices whose resolved salesperson is not a real salesperson
        # (e.g. the invoicing user set as fallback) are grouped under
        # 'Sin asignar' by _get_grouping_salesperson.

        # Filter by payment status
        if self.payment_status != 'all':
            domain.append(('payment_state', '=', self.payment_status))

        return domain

    def _get_selected_companies(self):
        """Return the companies effectively available to the report."""
        self.ensure_one()
        if self.company_ids:
            return self.company_ids & self.env.companies
        return self.env.companies

    def _get_report_move_types(self):
        """Return the move types included in the current report."""
        self.ensure_one()
        if self.invoice_type == 'out_refund':
            return ['out_refund']
        return ['out_invoice', 'out_refund']

    def _get_grouping_salesperson(self, invoice):
        """Return the salesperson used for grouping and export headers.

        Only partners flagged as salespersons are considered. Fallback
        partners injected by sales_commission_omax (invoice user, current
        user) are ignored so those invoices are grouped under
        'Sin asignar' instead of being silently dropped from the report.
        """
        self.ensure_one()
        for candidate in (invoice.salesperson_id, invoice.assigned_salesperson_id):
            if candidate and candidate.is_salesperson:
                return candidate
        return self.env['res.partner']

    def _get_invoices(self):
        """Get the final document universe shared by screen and export."""
        domain = self._get_invoices_domain()
        return self.env['account.move'].search(
            domain,
            order='salesperson_id, invoice_date, id',
        )

    def _get_salesperson_entries(self, invoices, salesperson_id):
        """Order one salesperson block, keeping linked refunds after the source invoice."""
        self.ensure_one()
        ordered_invoices = invoices.sorted(
            key=lambda invoice: (invoice.invoice_date or date.min, invoice.id)
        )
        invoice_ids = set(ordered_invoices.ids)
        inline_refunds_by_origin = {}

        for invoice in ordered_invoices:
            if invoice.move_type != 'out_refund' or not invoice.reversed_entry_id:
                continue

            origin_salesperson = self._get_grouping_salesperson(invoice.reversed_entry_id)
            origin_salesperson_id = origin_salesperson.id if origin_salesperson else False
            if (
                invoice.reversed_entry_id.id in invoice_ids
                and origin_salesperson_id == salesperson_id
            ):
                inline_refunds_by_origin.setdefault(
                    invoice.reversed_entry_id.id,
                    [],
                ).append(invoice)

        entries = []
        emitted_ids = set()

        for invoice in ordered_invoices:
            if invoice.id in emitted_ids:
                continue

            if invoice.move_type == 'out_refund' and invoice.reversed_entry_id:
                origin_salesperson = self._get_grouping_salesperson(invoice.reversed_entry_id)
                origin_salesperson_id = origin_salesperson.id if origin_salesperson else False
                if (
                    invoice.reversed_entry_id.id in invoice_ids
                    and origin_salesperson_id == salesperson_id
                ):
                    continue

            entries.append((invoice, False))
            emitted_ids.add(invoice.id)

            for refund in inline_refunds_by_origin.get(invoice.id, []):
                if refund.id not in emitted_ids:
                    entries.append((refund, True))
                    emitted_ids.add(refund.id)

        for invoice in ordered_invoices:
            if invoice.id not in emitted_ids:
                entries.append((invoice, False))
                emitted_ids.add(invoice.id)

        return entries

    def _prepare_invoice_data(self, invoice, inline_after_origin=False):
        """Convert one document into the structure consumed by PDF and Excel."""
        self.ensure_one()
        is_credit_note = invoice.move_type == 'out_refund'

        if is_credit_note:
            amount_untaxed = -abs(invoice.amount_untaxed)
            amount_tax = -abs(invoice.amount_tax)
            amount_total = -abs(invoice.amount_total)
        else:
            amount_untaxed = abs(invoice.amount_untaxed)
            amount_tax = abs(invoice.amount_tax)
            amount_total = abs(invoice.amount_total)

        number = invoice.name
        if is_credit_note and inline_after_origin:
            number = f"↳ {number}"

        return {
            'number': number,
            'date': str(invoice.invoice_date) if invoice.invoice_date else '',
            'partner': invoice.partner_id.name,
            'partner_vat': invoice.partner_id.vat or '',
            'currency': invoice.currency_id.name,
            'company': invoice.company_id.name,
            'amount_untaxed': amount_untaxed,
            'amount_tax': amount_tax,
            'amount_total': amount_total,
            'move_type': dict(invoice._fields['move_type'].selection).get(invoice.move_type),
            'payment_state': invoice.payment_state,
            'is_reversal_line': is_credit_note,
        }

    def _get_report_data(self):
        """Prepare data for the report grouped by salesperson.

        Handles multi-company reporting and correctly processes credit notes
        to avoid double-counting reversals.
        """
        invoices = self._get_invoices()

        if not invoices:
            raise UserError(_("No invoices found with the selected filters."))

        # Group invoices by salesperson
        data_by_salesperson = {}
        invoices_by_salesperson = {}
        grand_total_untaxed = 0.0
        grand_total_tax = 0.0
        grand_total = 0.0

        # Get company names for display
        selected_companies = self._get_selected_companies()
        company_names = ', '.join(selected_companies.mapped('name')) if len(selected_companies) > 1 else (
            selected_companies.name if selected_companies else self.env.company.name
        )

        for invoice in invoices:
            salesperson = self._get_grouping_salesperson(invoice)

            # Handle missing salesperson with a default value
            salesperson_id = salesperson.id if salesperson else False
            salesperson_name = salesperson.name if salesperson else 'Sin asignar'

            if salesperson_id not in data_by_salesperson:
                data_by_salesperson[salesperson_id] = {
                    'salesperson_name': salesperson_name,
                    'salesperson_id': salesperson_id,
                    'invoices': [],
                    'total_untaxed': 0.0,
                    'total_tax': 0.0,
                    'total': 0.0,
                }
                invoices_by_salesperson[salesperson_id] = self.env['account.move']

            invoices_by_salesperson[salesperson_id] |= invoice

        for salesperson_id, salesperson_data in data_by_salesperson.items():
            salesperson_invoices = invoices_by_salesperson[salesperson_id]

            for invoice, inline_after_origin in self._get_salesperson_entries(
                salesperson_invoices,
                salesperson_id,
            ):
                invoice_data = self._prepare_invoice_data(
                    invoice,
                    inline_after_origin=inline_after_origin,
                )
                salesperson_data['invoices'].append(invoice_data)
                salesperson_data['total_untaxed'] += invoice_data['amount_untaxed']
                salesperson_data['total_tax'] += invoice_data['amount_tax']
                salesperson_data['total'] += invoice_data['amount_total']

                grand_total_untaxed += invoice_data['amount_untaxed']
                grand_total_tax += invoice_data['amount_tax']
                grand_total += invoice_data['amount_total']

        return {
            'date_from': str(self.date_from),
            'date_to': str(self.date_to),
            'data_by_salesperson': list(data_by_salesperson.values()),
            'grand_total_untaxed': grand_total_untaxed,
            'grand_total_tax': grand_total_tax,
            'grand_total': grand_total,
            'company': self.env.company,
            'company_names': company_names,
            'companies_count': len(selected_companies) if selected_companies else 1,
            'invoice_count': len(invoices),
        }

    def action_view_on_screen(self):
        """Open invoice list view filtered by wizard criteria.

        This uses standard Odoo views and respects all security rules.
        Groups by effective_salesperson_id to show correct salesperson grouping.
        """
        self.ensure_one()
        invoices = self._get_invoices()
        selected_companies = self._get_selected_companies()
        domain = [('id', 'in', invoices.ids or [False])]

        # Build context with proper multi-company and grouping
        context = dict(self.env.context)
        context.update({
            'default_move_type': 'out_invoice',
            'search_default_posted': 1,
            'search_default_effective_salesperson': 1,  # Auto-group by effective salesperson
        })

        # Add allowed companies to context
        if selected_companies:
            context['allowed_company_ids'] = selected_companies.ids

        # Get the custom tree view
        tree_view = self.env.ref('sng_invoice_report.view_invoice_tree_effective_salesperson', False)
        tree_view_id = tree_view.id if tree_view else False

        return {
            'name': _('Invoice Report: %(date_from)s to %(date_to)s',
                     date_from=self.date_from, date_to=self.date_to),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,pivot,graph,form',
            'views': [
                (tree_view_id, 'list'),
                (False, 'pivot'),
                (False, 'graph'),
                (False, 'form'),
            ],
            'domain': domain,
            'context': context,
            'target': 'current',
        }

    def action_print_pdf(self):
        """Generate and download PDF report."""
        self.ensure_one()
        data = self._get_report_data()
        # Remove company object - it cannot be serialized properly
        if 'company' in data:
            del data['company']
        return self.env.ref('sng_invoice_report.action_report_invoice_salesperson').report_action(self, data=data)

    def action_print_excel(self):
        """Generate and download Excel report."""
        self.ensure_one()

        if not xlsxwriter:
            raise UserError(_("The 'xlsxwriter' Python library is required. Please install it with: pip install xlsxwriter"))

        data = self._get_report_data()

        # Create Excel file in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(_('Invoice Report')[:31])

        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
        })
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1,
        })
        salesperson_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#D9E2F3',
            'border': 1,
        })
        cell_format = workbook.add_format({
            'font_size': 10,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
        })
        number_format = workbook.add_format({
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'border': 1,
        })
        date_format = workbook.add_format({
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': 'yyyy-mm-dd',
            'border': 1,
        })
        # Red formats for reversed invoices
        cell_format_red = workbook.add_format({
            'font_size': 10,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_color': 'red',
        })
        number_format_red = workbook.add_format({
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'border': 1,
            'font_color': 'red',
        })
        date_format_red = workbook.add_format({
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': 'yyyy-mm-dd',
            'border': 1,
            'font_color': 'red',
        })
        # Gray italic formats for reversal/credit note lines
        cell_format_reversal = workbook.add_format({
            'font_size': 10,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_color': '#666666',
            'italic': True,
        })
        number_format_reversal = workbook.add_format({
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'border': 1,
            'font_color': '#666666',
            'italic': True,
        })
        date_format_reversal = workbook.add_format({
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': 'yyyy-mm-dd',
            'border': 1,
            'font_color': '#666666',
            'italic': True,
        })
        subtotal_format = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'bg_color': '#E2EFDA',
            'border': 1,
        })
        subtotal_label_format = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'bg_color': '#E2EFDA',
            'border': 1,
        })
        grand_total_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'bg_color': '#FFC000',
            'border': 2,
        })
        grand_total_label_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'align': 'right',
            'valign': 'vcenter',
            'bg_color': '#FFC000',
            'border': 2,
        })

        # Determine if we show company column
        show_company = data['companies_count'] > 1
        num_cols = 10 if show_company else 9
        last_col = num_cols - 1

        # Set column widths
        worksheet.set_column('A:A', 18)  # Invoice Number
        worksheet.set_column('B:B', 12)  # Date
        worksheet.set_column('C:C', 35)  # Customer
        worksheet.set_column('D:D', 15)  # VAT
        if show_company:
            worksheet.set_column('E:E', 20)  # Company
            worksheet.set_column('F:F', 18)  # Type
            worksheet.set_column('G:G', 8)   # Currency
            worksheet.set_column('H:H', 15)  # Untaxed Amount
            worksheet.set_column('I:I', 12)  # Tax
            worksheet.set_column('J:J', 15)  # Total
        else:
            worksheet.set_column('E:E', 18)  # Type
            worksheet.set_column('F:F', 8)   # Currency
            worksheet.set_column('G:G', 15)  # Untaxed Amount
            worksheet.set_column('H:H', 12)  # Tax
            worksheet.set_column('I:I', 15)  # Total

        row = 0

        # Title
        worksheet.merge_range(
            row, 0, row, last_col,
            _('Invoice Report by Salesperson'),
            title_format,
        )
        row += 1
        worksheet.merge_range(
            row, 0, row, last_col,
            _(
                '%(companies)s - From %(date_from)s to %(date_to)s',
                companies=data['company_names'],
                date_from=data['date_from'],
                date_to=data['date_to'],
            ),
            workbook.add_format({'align': 'center', 'font_size': 11}),
        )
        row += 2

        # Headers
        if show_company:
            headers = [
                _('Invoice #'),
                _('Date'),
                _('Customer'),
                _('VAT'),
                _('Company'),
                _('Type'),
                _('Currency'),
                _('Untaxed'),
                _('Tax'),
                _('Total'),
            ]
        else:
            headers = [
                _('Invoice #'),
                _('Date'),
                _('Customer'),
                _('VAT'),
                _('Type'),
                _('Currency'),
                _('Untaxed'),
                _('Tax'),
                _('Total'),
            ]
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        row += 1

        # Data by salesperson
        for sp_data in data['data_by_salesperson']:
            # Salesperson header
            worksheet.merge_range(
                row, 0, row, last_col,
                _('Salesperson: %(name)s', name=sp_data['salesperson_name']),
                salesperson_format,
            )
            row += 1

            # Invoice lines
            for inv in sp_data['invoices']:
                # Determine format based on invoice state
                is_reversed = inv.get('payment_state') == 'reversed'
                is_reversal_line = inv.get('is_reversal_line', False)

                if is_reversal_line:
                    # Gray italic for credit note lines
                    cf = cell_format_reversal
                    df = date_format_reversal
                    nf = number_format_reversal
                elif is_reversed:
                    # Red for reversed invoices
                    cf = cell_format_red
                    df = date_format_red
                    nf = number_format_red
                else:
                    # Normal format
                    cf = cell_format
                    df = date_format
                    nf = number_format

                col = 0
                worksheet.write(row, col, inv['number'], cf)
                col += 1
                worksheet.write(row, col, str(inv['date']), df)
                col += 1
                worksheet.write(row, col, inv['partner'], cf)
                col += 1
                worksheet.write(row, col, inv['partner_vat'], cf)
                col += 1
                if show_company:
                    worksheet.write(row, col, inv.get('company', ''), cf)
                    col += 1
                worksheet.write(row, col, inv['move_type'], cf)
                col += 1
                worksheet.write(row, col, inv['currency'], cf)
                col += 1
                worksheet.write(row, col, inv['amount_untaxed'], nf)
                col += 1
                worksheet.write(row, col, inv['amount_tax'], nf)
                col += 1
                worksheet.write(row, col, inv['amount_total'], nf)
                row += 1

            # Subtotal row for salesperson
            subtotal_merge_to = num_cols - 4
            worksheet.merge_range(
                row, 0, row, subtotal_merge_to,
                _('Subtotal - %(name)s', name=sp_data['salesperson_name']),
                subtotal_label_format,
            )
            worksheet.write(row, num_cols - 3, sp_data['total_untaxed'], subtotal_format)
            worksheet.write(row, num_cols - 2, sp_data['total_tax'], subtotal_format)
            worksheet.write(row, num_cols - 1, sp_data['total'], subtotal_format)
            row += 2

        # Grand total
        grand_total_merge_to = num_cols - 4
        worksheet.merge_range(
            row, 0, row, grand_total_merge_to,
            _('GRAND TOTAL'),
            grand_total_label_format,
        )
        worksheet.write(row, num_cols - 3, data['grand_total_untaxed'], grand_total_format)
        worksheet.write(row, num_cols - 2, data['grand_total_tax'], grand_total_format)
        worksheet.write(row, num_cols - 1, data['grand_total'], grand_total_format)

        workbook.close()
        output.seek(0)

        # Save the file to the wizard
        filename = f"invoice_report_{self.date_from}_{self.date_to}.xlsx"
        self.write({
            'excel_file': base64.b64encode(output.getvalue()),
            'excel_filename': filename,
        })

        # Return action to download
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/excel_file/{filename}?download=true',
            'target': 'new',
        }
