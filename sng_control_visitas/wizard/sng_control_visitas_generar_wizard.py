# -*- coding: utf-8 -*-
from odoo import _, fields, models


class SngControlVisitasGenerarWizard(models.TransientModel):
    _name = 'sng.control.visitas.generar.wizard'
    _description = 'Recalcular matriz de control de visitas'

    fecha = fields.Date(
        string='Mes a recalcular', required=True,
        default=lambda self: fields.Date.context_today(self),
        help='Cualquier día del mes; se regenera el mes completo.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)

    def action_generar(self):
        self.ensure_one()
        Linea = self.env['sng.control.visitas.linea']
        Linea._sng_generar_mes(self.fecha, self.company_id)
        periodo = self.fecha.strftime('%Y-%m')
        action = self.env['ir.actions.actions']._for_xml_id(
            'sng_control_visitas.action_sng_control_visitas_linea')
        action['domain'] = [('periodo', '=', periodo),
                            ('company_id', '=', self.company_id.id)]
        action['context'] = {'search_default_periodo': periodo}
        action['display_name'] = _('Matriz de control %s') % periodo
        return action
