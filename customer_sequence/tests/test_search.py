from odoo.tests.common import TransactionCase

class TestCustomerSearch(TransactionCase):

    def setUp(self):
        super(TestCustomerSearch, self).setUp()
        self.Partner = self.env['res.partner']
        self.partner = self.Partner.create({
            'name': 'Test Partner Search',
            'unique_id': 'TESTCODE123'
        })

    def test_search_by_code(self):
        # Search by exact code
        res = self.Partner.name_search('TESTCODE123')
        found_ids = [r[0] for r in res]
        self.assertIn(self.partner.id, found_ids, "Partner not found by unique_id using name_search")

    def test_search_by_partial_code(self):
        # Search by partial code
        res = self.Partner.name_search('TESTCODE')
        found_ids = [r[0] for r in res]
        self.assertIn(self.partner.id, found_ids, "Partner not found by partial unique_id using name_search")

    def test_search_prioritization(self):
        """Test that searching by unique_id is prioritized over other fields"""
        # Partner with unique_id '2086'
        partner_code = self.Partner.create({
            'name': 'Zubat',
            'unique_id': '2086',
        })
        
        # Partner with matching VAT/Name
        partner_other = self.Partner.create({
            'name': 'Wilberth',
            'vat': '602420862',
        })
        
        # Search for '2086'
        res = self.Partner.name_search('2086')
        ids = [r[0] for r in res]
        
        self.assertIn(partner_code.id, ids)
        self.assertIn(partner_other.id, ids)
        self.assertEqual(ids[0], partner_code.id, "Partner matching unique_id should be first")
