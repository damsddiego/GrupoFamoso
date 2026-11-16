# -*- coding: utf-8 -*-

import base64
import io
import re
import zipfile

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..models.sng_commission_monthly import MONTH_NAMES


class SngCommissionReportWiz(models.TransientModel):
    _name = 'sng.commission.report.wiz'
    _description = 'Reporte Consolidado de Comisiones del Mes'

    period = fields.Date(
        string='Mes',
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
        help='Cualquier día del mes: se toman todas las comisiones de ese mes.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        domain=lambda self: [('id', 'in', self.env.companies.ids)],
    )
    salesperson_ids = fields.Many2many(
        'res.partner',
        'sng_commission_report_wiz_partner_rel',
        'wiz_id',
        'partner_id',
        string='Vendedores',
        domain="[('is_salesperson', '=', True)]",
        help='Dejar vacío para incluir a todos los vendedores del mes.',
    )
    period_label = fields.Char(
        string='Periodo',
        compute='_compute_period_label',
    )
    monthly_count = fields.Integer(
        string='Comisiones encontradas',
        compute='_compute_monthly_count',
    )
    include_analysis = fields.Boolean(
        string='Incluir análisis',
        default=True,
        help='Agrega por vendedor de dónde salen los pagos (con el cuadre contra '
             'el monto de comisión), las notas de crédito sobre facturas ya '
             'cobradas, los cobros de meses anteriores y los reversos que no '
             'se devolvieron.',
    )

    @api.depends('period')
    def _compute_period_label(self):
        for wiz in self:
            if wiz.period:
                wiz.period_label = "%s %s" % (MONTH_NAMES.get(wiz.period.month, ''), wiz.period.year)
            else:
                wiz.period_label = ''

    @api.depends('period', 'company_id', 'salesperson_ids')
    def _compute_monthly_count(self):
        for wiz in self:
            wiz.monthly_count = len(wiz._get_monthlies()) if wiz.period and wiz.company_id else 0

    def _get_period(self):
        self.ensure_one()
        return self.period.replace(day=1)

    def _get_domain(self):
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('period', '=', self._get_period()),
        ]
        if self.salesperson_ids:
            domain.append(('salesperson_id', 'in', self.salesperson_ids.ids))
        return domain

    def _get_monthlies(self):
        """Comisiones mensuales del periodo/compañía, ordenadas por vendedor."""
        self.ensure_one()
        if not self.period or not self.company_id:
            return self.env['sng.commission.monthly']
        return self.env['sng.commission.monthly'].search(
            self._get_domain(), order='salesperson_id, id')

    def _get_subtitle(self):
        self.ensure_one()
        if self.salesperson_ids:
            sellers = ', '.join(self.salesperson_ids.mapped('name'))
        else:
            sellers = _('Todos')
        return _(
            'Periodo: %(period)s | Compañía: %(company)s | Vendedores: %(sellers)s',
            period=self.period_label, company=self.company_id.name, sellers=sellers,
        )

    def _get_totals(self, monthlies):
        return {
            'count': len(monthlies),
            'base_amount': sum(monthlies.mapped('base_amount')),
            'adjustment_amount': sum(monthlies.mapped('adjustment_amount')),
            'commission_amount': sum(monthlies.mapped('commission_amount')),
        }

    def _ensure_monthlies(self):
        self.ensure_one()
        monthlies = self._get_monthlies()
        if not monthlies:
            raise UserError(_(
                'No hay comisiones mensuales para %(company)s en %(period)s con los filtros indicados.',
                company=self.company_id.name, period=self.period_label,
            ))
        return monthlies

    def action_print_pdf(self):
        self.ensure_one()
        self._ensure_monthlies()
        return self.env.ref(
            'sng_sales_commission_payment.action_report_commission_consolidated_pdf'
        ).report_action(self, config=False)

    def action_print_xlsx(self):
        self.ensure_one()
        self._ensure_monthlies()
        return self.env.ref(
            'sng_sales_commission_payment.action_report_commission_consolidated_xlsx'
        ).report_action(self, config=False)

    @staticmethod
    def _safe_filename(text):
        return re.sub(r'[^\w\-. ]+', '_', text or '').strip() or 'sin_nombre'

    def action_print_individual_pdf(self):
        """Un archivo PDF por vendedor (para entregarle a cada uno la
        verificación de su comisión), usando el reporte por registro existente.

        Con un solo vendedor devuelve su PDF directo; con varios, un ZIP con
        un PDF independiente por vendedor.
        """
        self.ensure_one()
        monthlies = self._ensure_monthlies()
        report = self.env.ref('sng_sales_commission_payment.action_report_commission_monthly_pdf')
        # La casilla "Incluir análisis" viaja como `data` del render; con
        # report_action no se puede (con data no viajan los docids), por eso
        # también el caso de un solo vendedor se renderiza aquí.
        render_data = {'include_analysis': self.include_analysis}
        files = []
        for monthly in monthlies:
            pdf, _ext = report._render_qweb_pdf(report.report_name, res_ids=monthly.ids, data=render_data)
            filename = 'Comision %s - %s.pdf' % (
                self._safe_filename(monthly.salesperson_id.name),
                self._safe_filename(monthly.period_label),
            )
            files.append((filename, pdf))

        if len(files) == 1:
            name, content, mimetype = files[0][0], files[0][1], 'application/pdf'
        else:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for filename, pdf in files:
                    zf.writestr(filename, pdf)
            name = 'Comisiones por vendedor %s - %s.zip' % (
                self._safe_filename(self.period_label),
                self._safe_filename(self.company_id.name),
            )
            content, mimetype = buffer.getvalue(), 'application/zip'

        Attachment = self.env['ir.attachment']
        # Limpia los archivos anteriores del mismo usuario para no acumular adjuntos.
        Attachment.search([
            ('res_model', '=', self._name),
            ('create_uid', '=', self.env.uid),
        ]).unlink()
        attachment = Attachment.create({
            'name': name,
            'type': 'binary',
            'datas': base64.b64encode(content),
            'mimetype': mimetype,
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'download',
        }
