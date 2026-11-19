# -*- coding: utf-8 -*-
"""Base de las pruebas de cuadros de comisiones.

Corren en una copia de la base (necesitan dos compañías y, para las líneas,
pagos y facturas ya existentes). Todo va en periodos de 2031 para no chocar
con cuadros ni mensuales reales.
"""
import unittest

from odoo.tests import TransactionCase

TRAMOS = ((0.0, 0.0), (12000000.0, 2.75), (20000000.0, 3.0), (25000000.0, 3.5), (35000000.0, 4.0))


class ComisionGrupoCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Scheme = cls.env['sng.commission.scheme']
        cls.Monthly = cls.env['sng.commission.monthly']
        cls.Line = cls.env['sng.commission.payment.line']
        companias = cls.env['res.company'].search([], order='id', limit=2)
        if len(companias) < 2 or len(companias.mapped('currency_id')) > 1:
            raise unittest.SkipTest('Hacen falta dos compañías con la misma moneda.')
        cls.cia_a, cls.cia_b = companias
        cls.vendedor = cls.env['res.partner'].create({
            'name': 'Vendedor de prueba de cuadros',
            'is_salesperson': True,
        })

    @classmethod
    def _cuadro(cls, nombre, companias, desde, tramos=TRAMOS):
        return cls.Scheme.create({
            'name': nombre,
            'company_ids': [(6, 0, companias.ids)],
            'date_start': desde,
            'tier_ids': [(0, 0, {'min_amount': minimo, 'percentage': pct}) for minimo, pct in tramos],
        })

    def _linea(self, mensual, compania, base, tipo='commission'):
        """Línea de comisión en ``mensual`` sobre un par (cobro confirmado,
        factura publicada) que ya existe en ``compania`` y no tiene línea de
        ese tipo. El par no tiene por qué estar conciliado: aquí solo importa
        de qué compañía es el pago."""
        self.env.flush_all()
        self.env.cr.execute("""
            SELECT p.id, f.id
              FROM account_payment p,
                   LATERAL (SELECT m.id FROM account_move m
                             WHERE m.company_id = p.company_id AND m.move_type = 'out_invoice'
                               AND m.state = 'posted'
                             ORDER BY m.id DESC LIMIT 1) f
             WHERE p.company_id = %(company)s AND p.payment_type = 'inbound'
               AND p.state IN ('in_process', 'paid')
               AND NOT EXISTS (SELECT 1 FROM sng_commission_payment_line l
                                WHERE l.payment_id = p.id AND l.invoice_id = f.id AND l.line_type = %(tipo)s)
             ORDER BY p.id DESC LIMIT 1""", {'company': compania.id, 'tipo': tipo})
        par = self.env.cr.fetchone()
        if not par:
            self.skipTest('La base no tiene un cobro y una factura libres en %s.' % compania.name)
        return self.Line.create({
            'monthly_id': mensual.id,
            'payment_id': par[0],
            'invoice_id': par[1],
            'salesperson_id': mensual.salesperson_id.id,
            'line_type': tipo,
            'payment_amount': base,
            'invoice_amount_untaxed': base,
            'invoice_amount_total': base,
            'commission_base': base,
        })

    def _leer_como_cliente(self, registro, tipo='form'):
        """Lee el registro como el cliente web al abrir la vista: todos los
        campos del arch, con el nombre de cada relacional. Devuelve el dict."""
        from lxml import etree

        def spec_de(modelo, raiz):
            spec = {}
            for nodo in raiz.iter('field'):
                padre, anidado = nodo.getparent(), False
                while padre is not None and padre is not raiz:
                    anidado = anidado or padre.tag == 'field'
                    padre = padre.getparent()
                if anidado:
                    continue
                campo = modelo._fields[nodo.get('name')]
                if campo.type == 'many2one':
                    spec[campo.name] = {'fields': {'display_name': {}}}
                elif campo.type in ('one2many', 'many2many'):
                    lista = nodo.find('list')
                    spec[campo.name] = {'fields': (
                        spec_de(modelo.env[campo.comodel_name], lista) if lista is not None
                        else {'display_name': {}})}
                else:
                    spec[campo.name] = {}
            return spec

        arch = etree.fromstring(registro.get_view(view_type=tipo)['arch'])
        return registro.web_read(spec_de(registro, arch))[0]
