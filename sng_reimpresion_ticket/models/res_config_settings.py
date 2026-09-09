from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Parametros de sistema, no por compania: la base en tiempo real es una sola
    # para todas las companias que imprimen.
    sng_reimpresion_webhook_url = fields.Char(
        string='URL del webhook de reimpresion',
        config_parameter='sng_reimpresion.webhook_url',
        help='Endpoint de n8n que escribe la autorizacion en Firebase. '
             'Ejemplo: https://n8n.facturaexpert.com/webhook/reprint-approval',
    )
    sng_reimpresion_token = fields.Char(
        string='Token compartido',
        config_parameter='sng_reimpresion.token',
        help='Clave que n8n valida antes de escribir la autorizacion. Es una '
             'credencial al portador: quien la tenga puede autorizar '
             'reimpresiones sin pasar por Odoo. Solo deberia poder verla el '
             'grupo Ajustes.',
    )
    sng_reimpresion_print_url = fields.Char(
        string='URL de impresion (opcional)',
        config_parameter='sng_reimpresion.print_url',
        help='A donde se reenvian las ordenes que nunca llegaron a imprimirse. '
             'Dejar vacio es lo normal: se toma de la regla de automatizacion '
             '"Imprimir ticket al confirmar orden", que es la misma que ya '
             'dispara Odoo al confirmar. Solo llenarlo para apuntar a otro '
             'endpoint.',
    )
    sng_reimpresion_timeout = fields.Integer(
        string='Tiempo de espera (segundos)',
        config_parameter='sng_reimpresion.timeout',
        default=15,
        help='Cuanto espera Odoo la respuesta del webhook antes de darla por '
             'fallida.',
    )
