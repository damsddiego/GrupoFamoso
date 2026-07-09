# -*- coding: utf-8 -*-

from odoo import _, fields, models


class SngCommercialPlanExportWizard(models.TransientModel):
    _name = 'sng.commercial.plan.export.wizard'
    _description = 'SNG Commercial Plan Export Wizard'

    plan_id = fields.Many2one(
        'sng.commercial.plan',
        string='Plan',
        required=True,
        readonly=True,
    )
    file_data = fields.Binary(
        string='Archivo',
        readonly=True,
    )
    file_name = fields.Char(
        string='Nombre Archivo',
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('done', 'Listo'),
        ],
        default='draft',
        readonly=True,
    )

    def action_generate_file(self):
        self.ensure_one()
        filename, file_data = self.plan_id.generate_xlsx_file()
        self.write({
            'file_name': filename,
            'file_data': file_data,
            'state': 'done',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exportar Plan Comercial'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
