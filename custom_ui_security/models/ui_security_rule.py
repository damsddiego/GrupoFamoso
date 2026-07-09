# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
UI Security Rule - Modelo para Fase 2
======================================

Este modelo está preparado pero NO ACTIVO en Fase 1.

Para activarlo:
1. Descomentar la importación en models/__init__.py
2. Descomentar la vista en __manifest__.py
3. Implementar el motor de aplicación dinámica (ver comentarios abajo)

ARQUITECTURA PROPUESTA PARA FASE 2:
-----------------------------------
Este modelo permitirá definir reglas configurables para controlar la UI
sin necesidad de modificar código Python o XML para cada caso.

Funcionamiento:
- Los usuarios configuran reglas desde la interfaz
- Un hook (fields_view_get) procesa las reglas activas
- Se modifican las vistas dinámicamente antes de enviarlas al cliente
- Se puede usar cache para optimizar performance
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class UiSecurityRule(models.Model):
    """
    Modelo de configuración para reglas de seguridad de UI.

    Permite definir qué elementos de interfaz (campos, botones, pestañas, etc.)
    deben ocultarse o volverse readonly según grupos de usuario.
    """

    _name = 'ui.security.rule'
    _description = 'Regla de Seguridad de Interfaz'
    _order = 'sequence, model_id, id'

    # ==========================================
    # CAMPOS BÁSICOS
    # ==========================================

    name = fields.Char(
        string='Nombre de la Regla',
        required=True,
        help='Nombre descriptivo de la regla (ej: "Ocultar costo de producto")'
    )

    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está desactivado, la regla no se aplicará'
    )

    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de aplicación cuando hay múltiples reglas'
    )

    note = fields.Text(
        string='Notas',
        help='Documentación interna sobre el propósito de esta regla'
    )

    # ==========================================
    # MODELO Y OBJETIVO
    # ==========================================

    model_id = fields.Many2one(
        'ir.model',
        string='Modelo',
        required=True,
        ondelete='cascade',
        help='Modelo de Odoo donde se aplicará la regla (ej: product.template)'
    )

    model_name = fields.Char(
        string='Nombre Técnico del Modelo',
        related='model_id.model',
        store=True,
        readonly=True
    )

    target_type = fields.Selection(
        [
            ('field', 'Campo'),
            ('button', 'Botón'),
            ('page', 'Pestaña/Página'),
            ('notebook', 'Notebook'),
            ('group', 'Grupo XML'),
        ],
        string='Tipo de Elemento',
        required=True,
        default='field',
        help='Tipo de elemento de interfaz a controlar'
    )

    target_name = fields.Char(
        string='Nombre Técnico',
        required=True,
        help='Nombre técnico del campo, botón o elemento XML (ej: "standard_price")'
    )

    # ==========================================
    # TIPO DE REGLA Y ACCIÓN
    # ==========================================

    rule_type = fields.Selection(
        [
            ('hide', 'Ocultar elemento'),
            ('readonly', 'Solo lectura'),
            ('invisible', 'Invisible (mantiene espacio)'),
            ('required', 'Campo requerido'),
            ('optional', 'Campo opcional'),
        ],
        string='Tipo de Regla',
        required=True,
        default='hide',
        help='Acción a aplicar sobre el elemento'
    )

    # ==========================================
    # ÁMBITO DE APLICACIÓN
    # ==========================================

    view_types = fields.Selection(
        [
            ('all', 'Todas las vistas'),
            ('form', 'Solo formulario'),
            ('tree', 'Solo lista/árbol'),
            ('kanban', 'Solo kanban'),
            ('search', 'Solo búsqueda'),
            ('calendar', 'Solo calendario'),
            ('pivot', 'Solo tabla dinámica'),
            ('graph', 'Solo gráfico'),
        ],
        string='Ámbito de Vistas',
        default='all',
        required=True,
        help='En qué tipo de vista se aplicará la regla'
    )

    # ==========================================
    # GRUPOS DE SEGURIDAD
    # ==========================================

    group_mode = fields.Selection(
        [
            ('hide_for', 'Ocultar para grupos seleccionados'),
            ('show_only_for', 'Mostrar solo para grupos seleccionados'),
        ],
        string='Modo de Grupo',
        default='show_only_for',
        required=True,
        help='Define si los grupos tienen o no acceso al elemento'
    )

    group_ids = fields.Many2many(
        'res.groups',
        'ui_security_rule_group_rel',
        'rule_id',
        'group_id',
        string='Grupos',
        help='Grupos de usuarios afectados por esta regla'
    )

    # ==========================================
    # CAMPOS COMPUTADOS Y TÉCNICOS
    # ==========================================

    effective_users_count = fields.Integer(
        string='Usuarios Afectados',
        compute='_compute_effective_users_count',
        help='Número de usuarios afectados por esta regla'
    )

    @api.depends('group_ids')
    def _compute_effective_users_count(self):
        """Calcula cuántos usuarios están afectados por esta regla."""
        for rule in self:
            if rule.group_ids:
                rule.effective_users_count = self.env['res.users'].search_count([
                    ('groups_id', 'in', rule.group_ids.ids)
                ])
            else:
                rule.effective_users_count = 0

    # ==========================================
    # VALIDACIONES
    # ==========================================

    @api.constrains('target_name', 'model_id', 'target_type')
    def _check_target_exists(self):
        """
        Valida que el campo o elemento objetivo exista en el modelo.
        NOTA: Esta validación es básica. En Fase 2 se debe mejorar.
        """
        for rule in self:
            if rule.target_type == 'field':
                # Verificar que el campo existe en el modelo
                model = self.env[rule.model_name]
                if rule.target_name not in model._fields:
                    raise ValidationError(
                        f"El campo '{rule.target_name}' no existe en el modelo '{rule.model_name}'"
                    )

    @api.constrains('group_ids')
    def _check_has_groups(self):
        """Valida que se hayan seleccionado grupos."""
        for rule in self:
            if not rule.group_ids:
                raise ValidationError(
                    "Debe seleccionar al menos un grupo para aplicar la regla"
                )

    # ==========================================
    # MÉTODOS DE NEGOCIO
    # ==========================================

    def _get_groups_xmlid_string(self):
        """
        Retorna una cadena con los XML IDs de los grupos separados por coma.
        Útil para construir el atributo 'groups' en XML.

        Retorna:
            str: "base.group_user,base.group_system"
        """
        self.ensure_one()
        group_xmlids = []
        for group in self.group_ids:
            xmlid = self.env['ir.model.data'].search([
                ('model', '=', 'res.groups'),
                ('res_id', '=', group.id)
            ], limit=1)
            if xmlid:
                group_xmlids.append(f"{xmlid.module}.{xmlid.name}")
        return ','.join(group_xmlids)

    # ==========================================
    # MOTOR DE APLICACIÓN (FASE 2)
    # ==========================================

    """
    IMPLEMENTACIÓN PROPUESTA PARA FASE 2:

    def apply_rules_to_view(self, model_name, view_type, arch):
        '''
        Aplica las reglas activas a una vista específica.

        Este método debe ser llamado desde un override de fields_view_get
        en cada modelo objetivo, o mediante un hook global.

        Args:
            model_name (str): Nombre técnico del modelo
            view_type (str): Tipo de vista (form, tree, etc.)
            arch (etree.Element): Arquitectura XML de la vista

        Returns:
            etree.Element: Arquitectura modificada
        '''
        from lxml import etree

        # Buscar reglas aplicables
        domain = [
            ('active', '=', True),
            ('model_name', '=', model_name),
            '|',
            ('view_types', '=', 'all'),
            ('view_types', '=', view_type),
        ]

        rules = self.search(domain, order='sequence')

        for rule in rules:
            groups_str = rule._get_groups_xmlid_string()

            if rule.target_type == 'field':
                # Buscar el campo en la vista
                field_nodes = arch.xpath(f"//field[@name='{rule.target_name}']")

                for field_node in field_nodes:
                    if rule.rule_type == 'hide':
                        # Agregar atributo groups
                        if rule.group_mode == 'show_only_for':
                            field_node.set('groups', groups_str)
                        else:
                            # Para hide_for, necesitamos lógica inversa
                            # Esto requiere más complejidad
                            pass

                    elif rule.rule_type == 'readonly':
                        # Agregar atributo readonly condicional
                        # Esto puede requerir attrs o invisible
                        pass

            elif rule.target_type == 'button':
                # Lógica similar para botones
                button_nodes = arch.xpath(f"//button[@name='{rule.target_name}']")
                # ... aplicar regla
                pass

        return arch


    # HOOK GLOBAL PROPUESTO:

    @api.model
    def _fields_view_get_hook(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        '''
        Override de fields_view_get para aplicar reglas dinámicas.

        Este método debe extenderse en un mixin aplicable a todos los modelos,
        o mediante un monkey patch controlado.
        '''
        result = super()._fields_view_get_hook(view_id, view_type, toolbar, submenu)

        # Aplicar reglas de UI Security
        rule_model = self.env['ui.security.rule']
        arch_tree = etree.fromstring(result['arch'])
        arch_tree = rule_model.apply_rules_to_view(self._name, view_type, arch_tree)
        result['arch'] = etree.tostring(arch_tree, encoding='unicode')

        return result
    """

    # ==========================================
    # VISTAS Y ACCIONES
    # ==========================================

    def action_view_affected_users(self):
        """Abre una vista con los usuarios afectados por esta regla."""
        self.ensure_one()
        return {
            'name': f'Usuarios afectados por: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'view_mode': 'tree,form',
            'domain': [('groups_id', 'in', self.group_ids.ids)],
            'context': {'create': False, 'edit': False},
        }
