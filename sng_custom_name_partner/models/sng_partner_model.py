from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    commercial_name = fields.Char(
        string='Nombre Comercial',
        help='Nombre comercial del contacto',
        searchable=True
    )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Sobrescribir name_search para incluir búsqueda por nombre comercial."""
        args = args or []
        if name:
            # Buscar primero por los criterios estándar
            partners = self.search(['|', '|', '|', '|', '|',
                ('complete_name', operator, name),
                ('ref', operator, name),
                ('email', operator, name),
                ('vat', operator, name),
                ('company_registry', operator, name),
                ('commercial_name', operator, name),
            ] + args, limit=limit)
            return [(partner.id, partner.display_name) for partner in partners]
        return super(ResPartner, self).name_search(name, args, operator, limit)
