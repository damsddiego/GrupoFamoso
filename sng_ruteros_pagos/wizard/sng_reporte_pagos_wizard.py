# -*- coding: utf-8 -*-
import io

import xlsxwriter  # dependencia estándar de Odoo (exportación nativa a xlsx)

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from ..models.account_payment import SNG_SOLO_RUTEROS


class SngRuterosReportePagos(models.TransientModel):
    _name = 'sng.ruteros.reporte.pagos'
    _description = 'Reporte de recibos de ruteros por diario y vendedor'

    fecha_desde = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    fecha_hasta = fields.Date(
        string='Hasta', required=True,
        default=fields.Date.context_today)
    company_ids = fields.Many2many(
        'res.company', string='Compañías', required=True,
        default=lambda self: self.env.companies,
        domain=lambda self: [('id', 'in', self.env.user.company_ids.ids)],
        help='El reporte separa cada compañía en su propia sección.')
    journal_ids = fields.Many2many(
        'account.journal', string='Diarios',
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', 'in', company_ids)]",
        help='Vacío = todos los diarios de las compañías seleccionadas.')
    vendedor_ids = fields.Many2many(
        'res.partner', string='Vendedores',
        domain="[('is_salesperson', '=', True)]",
        help='Vacío = todos los vendedores. El vendedor es un contacto '
             '(lógica de sales_commission_omax), no un usuario.')
    agrupar = fields.Selection(
        [
            ('diario_vendedor', 'Diario → Vendedor'),
            ('vendedor_diario', 'Vendedor → Diario'),
        ],
        string='Agrupar por', required=True, default='diario_vendedor')
    solo_confirmados = fields.Boolean(
        string='Solo confirmados', default=True,
        help='Incluir únicamente pagos En proceso / Pagado. Desmarcar para '
             'incluir también borradores.')

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def _get_payments(self):
        self.ensure_one()
        domain = [
            ('sng_from_app', '=', True),
            SNG_SOLO_RUTEROS,  # este reporte es la liquidación de ruta
            ('company_id', 'in', self.company_ids.ids),
            ('date', '>=', self.fecha_desde),
            ('date', '<=', self.fecha_hasta),
        ]
        if self.solo_confirmados:
            domain.append(('state', 'in', ('in_process', 'paid')))
        else:
            domain.append(('state', 'not in', ('canceled', 'rejected')))
        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        if self.vendedor_ids:
            domain.append(('sng_vendedor_id', 'in', self.vendedor_ids.ids))
        return self.env['account.payment'].search(
            domain, order='company_id, journal_id, sng_vendedor_id, date, id')

    def _fmt(self, monto, company):
        return formatLang(self.env, monto, currency_obj=company.currency_id)

    def _periodo(self):
        return '%s — %s' % (
            self.fecha_desde.strftime('%d/%m/%Y'),
            self.fecha_hasta.strftime('%d/%m/%Y'))

    def _datos_agrupados(self):
        """Compañía → Diario → Vendedor (o Vendedor → Diario), con subtotales.

        Cada compañía es una sección independiente con sus propios totales en
        su propia moneda; no se mezclan montos entre compañías.
        """
        self.ensure_one()
        payments = self._get_payments()
        if not payments:
            raise UserError(_(
                'No hay recibos de la app en el rango seleccionado.'))
        if self.agrupar == 'diario_vendedor':
            campo1, campo2 = 'journal_id', 'sng_vendedor_id'
        else:
            campo1, campo2 = 'sng_vendedor_id', 'journal_id'
        sin = {'journal_id': _('(sin diario)'),
               'sng_vendedor_id': _('(sin vendedor)')}

        companias = []
        for company, pagos_c in payments.grouped('company_id').items():
            grupos = []
            for rec1, pagos1 in pagos_c.grouped(campo1).items():
                subgrupos = []
                for rec2, pagos2 in pagos1.grouped(campo2).items():
                    subgrupos.append({
                        'nombre': rec2.display_name or sin[campo2],
                        'cantidad': len(pagos2),
                        'total': sum(pagos2.mapped('amount')),
                        'total_fmt': self._fmt(
                            sum(pagos2.mapped('amount')), company),
                        'pagos': [{
                            'fecha': p.date,
                            'recibo': p.display_name,
                            'cliente': p.partner_id.display_name or '',
                            'metodo': p.sng_metodo_pago or '',
                            'referencia': p.sng_referencia or '',
                            'estado': dict(p._fields['state'].get_description(
                                self.env)['selection']).get(p.state, p.state),
                            'monto': p.amount,
                            'monto_fmt': self._fmt(p.amount, company),
                        } for p in pagos2],
                    })
                grupos.append({
                    'nombre': rec1.display_name or sin[campo1],
                    'cantidad': len(pagos1),
                    'total': sum(pagos1.mapped('amount')),
                    'total_fmt': self._fmt(
                        sum(pagos1.mapped('amount')), company),
                    'subgrupos': subgrupos,
                })
            companias.append({
                'nombre': company.name,
                'cantidad': len(pagos_c),
                'total': sum(pagos_c.mapped('amount')),
                'total_fmt': self._fmt(sum(pagos_c.mapped('amount')), company),
                'grupos': grupos,
            })
        etiquetas = dict(self._fields['agrupar'].get_description(
            self.env)['selection'])
        return {
            'periodo': self._periodo(),
            'agrupacion': etiquetas[self.agrupar],
            'companias': companias,
            'cantidad_total': len(payments),
        }

    # ------------------------------------------------------------------
    # Salidas
    # ------------------------------------------------------------------

    def action_ver_pantalla(self):
        """Lista nativa agrupada (expandible, con subtotales de Odoo)."""
        self.ensure_one()
        payments = self._get_payments()
        if self.agrupar == 'diario_vendedor':
            group_by = ['journal_id', 'sng_vendedor_id']
        else:
            group_by = ['sng_vendedor_id', 'journal_id']
        # Con más de una compañía, esta es el primer nivel de agrupación.
        if len(payments.company_id) > 1:
            group_by.insert(0, 'company_id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recibos Ruteros %s', self._periodo()),
            'res_model': 'account.payment',
            'view_mode': 'list,pivot,form',
            'domain': [('id', 'in', payments.ids)],
            'context': {'group_by': group_by},
            'views': [
                (self.env.ref(
                    'sng_ruteros_pagos.view_ruteros_recibo_list').id, 'list'),
                (False, 'pivot'),
                (False, 'form'),
            ],
        }

    def action_imprimir_pdf(self):
        self.ensure_one()
        self._datos_agrupados()  # valida que haya datos antes de renderizar
        return self.env.ref(
            'sng_ruteros_pagos.action_reporte_pagos_pdf').report_action(self)

    def action_exportar_excel(self):
        self.ensure_one()
        datos = self._datos_agrupados()
        buffer = io.BytesIO()
        libro = xlsxwriter.Workbook(buffer, {'in_memory': True})
        hoja = libro.add_worksheet(_('Pagos Ruteros'))

        f_titulo = libro.add_format({'bold': True, 'font_size': 14})
        f_sub = libro.add_format({'italic': True, 'font_color': '#666666'})
        f_comp = libro.add_format(
            {'bold': True, 'font_size': 12, 'bg_color': '#4472C4',
             'font_color': 'white', 'border': 1})
        f_comp_monto = libro.add_format(
            {'bold': True, 'font_size': 12, 'bg_color': '#4472C4',
             'font_color': 'white', 'border': 1, 'num_format': '#,##0.00'})
        f_grupo = libro.add_format(
            {'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        f_subgrupo = libro.add_format({'bold': True, 'bg_color': '#F2F2F2'})
        f_cab = libro.add_format(
            {'bold': True, 'bottom': 1, 'bg_color': '#EEEEEE'})
        f_monto = libro.add_format({'num_format': '#,##0.00'})
        f_monto_neg = libro.add_format({'num_format': '#,##0.00', 'bold': True})
        f_fecha = libro.add_format({'num_format': 'dd/mm/yyyy'})

        anchos = [12, 22, 40, 16, 20, 14, 14]
        for col, ancho in enumerate(anchos):
            hoja.set_column(col, col, ancho)

        hoja.write(0, 0, _('Recibos Ruteros — %s', datos['periodo']), f_titulo)
        hoja.write(1, 0, _('Agrupado por: %s', datos['agrupacion']), f_sub)
        fila = 3
        cabeceras = [_('Fecha'), _('Recibo'), _('Cliente'), _('Método'),
                     _('Referencia'), _('Estado'), _('Monto')]
        for compania in datos['companias']:
            hoja.merge_range(
                fila, 0, fila, 5,
                '%s (%s %s)' % (compania['nombre'], compania['cantidad'],
                                _('recibos')),
                f_comp)
            hoja.write_number(fila, 6, compania['total'], f_comp_monto)
            fila += 1
            for grupo in compania['grupos']:
                hoja.merge_range(fila, 0, fila, 5, grupo['nombre'], f_grupo)
                hoja.write_number(fila, 6, grupo['total'], f_monto_neg)
                fila += 1
                for sub in grupo['subgrupos']:
                    hoja.merge_range(
                        fila, 0, fila, 5,
                        '    %s (%s)' % (sub['nombre'], sub['cantidad']),
                        f_subgrupo)
                    hoja.write_number(fila, 6, sub['total'], f_monto_neg)
                    fila += 1
                    for col, texto in enumerate(cabeceras):
                        hoja.write(fila, col, texto, f_cab)
                    fila += 1
                    for p in sub['pagos']:
                        hoja.write_datetime(fila, 0, p['fecha'], f_fecha)
                        hoja.write(fila, 1, p['recibo'])
                        hoja.write(fila, 2, p['cliente'])
                        hoja.write(fila, 3, p['metodo'])
                        hoja.write(fila, 4, p['referencia'])
                        hoja.write(fila, 5, p['estado'])
                        hoja.write_number(fila, 6, p['monto'], f_monto)
                        fila += 1
                    fila += 1
            fila += 1
        libro.close()

        nombre = 'recibos_ruteros_%s_%s.xlsx' % (
            self.fecha_desde.strftime('%Y%m%d'),
            self.fecha_hasta.strftime('%Y%m%d'))
        adjunto = self.env['ir.attachment'].create({
            'name': nombre,
            'raw': buffer.getvalue(),
            'mimetype': ('application/vnd.openxmlformats-officedocument'
                         '.spreadsheetml.sheet'),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % adjunto.id,
            'target': 'self',
        }
