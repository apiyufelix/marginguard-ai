import unittest
from decimal import Decimal
from marginguard.rules import underbilling

class FinancialRules(unittest.TestCase):
    def test_financial_rounding(self):
        self.assertEqual(underbilling(3,'10.005','10'), Decimal('0.02'))
    def test_clean_and_overbilling(self):
        self.assertEqual(underbilling(20,100,100),0)
        self.assertEqual(underbilling(20,100,110),0)
    def test_partial_billing(self):
        self.assertEqual(underbilling(4,20,18),Decimal('8.00'))
    def test_invalid_inputs(self):
        for args in [(0,2,1),(1,-2,1),(1,2,-1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                underbilling(*args)

if __name__=='__main__': unittest.main()
