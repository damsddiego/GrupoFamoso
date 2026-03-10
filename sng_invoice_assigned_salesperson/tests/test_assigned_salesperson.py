from odoo.tests.common import TransactionCase

class TestAssignedSalesperson(TransactionCase):

    def setUp(self):
        super(TestAssignedSalesperson, self).setUp()
        self.partner_model = self.env['res.partner']
        self.move_model = self.env['account.move']

        # Create a salesperson contact
        self.salesperson = self.partner_model.create({
            'name': 'Salesperson A',
            'is_salesperson': True,
        })

        # Create a customer with assigned salesperson
        self.customer = self.partner_model.create({
            'name': 'Customer B',
            'assigned_salesperson_id': self.salesperson.id,
        })

    def test_invoice_assigned_salesperson(self):
        """Test that assigned_salesperson_id is populated on invoice creation"""
        invoice = self.move_model.create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': '2023-01-01',
        })
        
        # Verify the field is populated
        self.assertEqual(invoice.assigned_salesperson_id, self.salesperson)
