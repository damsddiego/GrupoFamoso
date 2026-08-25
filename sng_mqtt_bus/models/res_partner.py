# -*- coding: utf-8 -*-
"""Emite eventos MQTT cuando cambian los CLIENTES (res.partner).

La app recibe {"id": <partner_id>, "accion": ...} en el topic
'<prefix>/clientes' y sincroniza ese cliente puntual por RPC. Los contactos
marcados como vendedor (is_salesperson) no se emiten.
"""
from odoo import api, models

# Escrituras que no le interesan a la app (chatter, actividades, presencia):
# si el write toca SOLO estos campos, no se emite evento.
_CAMPOS_IGNORADOS = (
    'message_', 'activity_', 'im_status', 'website_message_',
    'partner_gid', 'contact_address', 'user_livechat_username',
)


def _solo_campos_ignorados(vals):
    return vals and all(
        any(campo.startswith(p) for p in _CAMPOS_IGNORADOS) for campo in vals
    )


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _sng_mqtt_emitir(self, accion):
        bus = self.env['sng.mqtt.bus']
        for partner in self:
            if partner.is_salesperson:
                continue
            bus.publicar('clientes', {'id': partner.id, 'accion': accion})

    @api.model_create_multi
    def create(self, vals_list):
        registros = super().create(vals_list)
        registros._sng_mqtt_emitir('creado')
        return registros

    def write(self, vals):
        resultado = super().write(vals)
        if _solo_campos_ignorados(vals):
            return resultado
        if 'active' in vals:
            accion = 'archivado' if not vals['active'] else 'desarchivado'
        else:
            accion = 'modificado'
        self._sng_mqtt_emitir(accion)
        return resultado

    def unlink(self):
        # Emitir ANTES del borrado (después ya no existen los ids); la
        # publicación real igual sale post-commit, así que si el unlink
        # falla y hace rollback, no se emite nada.
        self._sng_mqtt_emitir('eliminado')
        return super().unlink()
