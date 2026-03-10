# -*- coding: utf-8 -*-
"""
AbstractModel para el reporte QWeb PDF del Estado de Cuenta de Clientes.

_get_report_values recibe los datos ya calculados por el wizard y los
prepara para el template QWeb.
"""

from datetime import date, datetime

from odoo import api, models


class CustomerStatementReport(models.AbstractModel):
    _name = 'report.sng_customer_statement.report_customer_statement_doc'
    _description = 'Reporte PDF: Estado de Cuenta de Clientes'

    @staticmethod
    def _format_date_dmy(value):
        """Formatea fecha a dd/mm/yyyy para el template QWeb."""
        if not value:
            return ''
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value.strftime('%d/%m/%Y')
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return ''
            if len(raw) == 10 and raw[2] == '/' and raw[5] == '/':
                return raw
            for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
                try:
                    return datetime.strptime(raw, fmt).strftime('%d/%m/%Y')
                except ValueError:
                    continue
            return raw
        return str(value)

    @staticmethod
    def _format_amount(value):
        """Formatea montos con separador de miles: 1.234.567,89."""
        try:
            amount = float(value or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        formatted = f"{amount:,.2f}"
        return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')

    def _resolve_wizard_for_report(self, docids, data):
        """
        Obtiene el wizard origen del reporte de forma robusta.
        Prioridad:
          1) docids del reporte
          2) wizard_id en data
          3) active_id/active_ids en contexto
        """
        wizard_model = self.env['sng.customer.statement.wizard']
        docs = wizard_model.browse(docids or [])

        if docs:
            return docs[:1], docs

        wizard_id = False
        if isinstance(data, dict):
            wizard_id = data.get('wizard_id')
            nested = data.get('data')
            if not wizard_id and isinstance(nested, dict):
                wizard_id = nested.get('wizard_id')
        if wizard_id:
            wiz = wizard_model.browse(wizard_id).exists()
            if wiz:
                return wiz[:1], wiz

        active_ids = self.env.context.get('active_ids') or []
        active_id = self.env.context.get('active_id')
        if active_id and active_id not in active_ids:
            active_ids = [active_id] + list(active_ids)
        docs = wizard_model.browse(active_ids).exists()
        if docs:
            return docs[:1], docs
        return wizard_model.browse(), wizard_model.browse()

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Entrega los valores al template QWeb.

        Args:
            docids: IDs del wizard (TransientModel)
            data: dict serializable con los datos del reporte (calculado en wizard)

        Returns:
            dict con 'docs', 'data', 'company', 'report_mode', etc.
        """
        wizard, docs = self._resolve_wizard_for_report(docids, data or {})
        report_data = {}
        if wizard:
            # Recalcula siempre desde el wizard para respetar filtros/modo activos
            # y evitar PDFs con payload incompleto.
            report_data = wizard._get_report_data()
            report_data.pop('company', None)

        return {
            'doc_ids': docs.ids,
            'doc_model': 'sng.customer.statement.wizard',
            'docs': docs,
            'data': report_data,
            'company': self.env.company,
            # Helpers de formato para el template
            'formatLang': self.env['ir.qweb.field.float'].value_to_html,
            'fmt_date': self._format_date_dmy,
            'fmt_amount': self._format_amount,
        }
