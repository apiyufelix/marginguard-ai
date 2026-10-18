from decimal import Decimal as D
import unittest
from marginguard.workflow import CasePolicyError, money, required_text, transition_amount, validate_recovery

class InvestigationPolicy(unittest.TestCase):
    def test_money_is_exact_and_rejects_unrepresentable_values(self):
        self.assertEqual(money('10.10'),D('10.10'))
        self.assertEqual(money('10000000000000000000.01'),D('10000000000000000000.01'))
        for value in ('NaN','Infinity','-1','1.001','1e2','$10','1,000','',None):
            with self.subTest(value=value),self.assertRaises(CasePolicyError):money(value)

    def test_confirmed_amount_is_bounded(self):
        self.assertEqual(transition_amount('investigating','confirmed',D('100'),None,D('0'),'80'),D('80'))
        for value in ('0','100.01'):
            with self.assertRaises(CasePolicyError):transition_amount('investigating','confirmed',D('100'),None,D('0'),value)

    def test_cannot_skip_investigation_or_dismiss_a_confirmed_case(self):
        for current,target in [('open','confirmed'),('open','resolved'),('confirmed','dismissed'),('dismissed','confirmed')]:
            with self.subTest(current=current,target=target),self.assertRaises(CasePolicyError):
                transition_amount(current,target,D('100'),D('100'),D('0'),'100')

    def test_unrecovered_closure_requires_explicit_choice(self):
        with self.assertRaises(CasePolicyError):transition_amount('confirmed','resolved',D('100'),D('80'),D('20'))
        self.assertEqual(transition_amount('confirmed','resolved',D('100'),D('80'),D('20'),close_with_balance=True),D('80'))
        self.assertEqual(transition_amount('confirmed','resolved',D('100'),D('80'),D('80')),D('80'))

    def test_withdrawing_confirmation_requires_reversing_recoveries(self):
        with self.assertRaises(CasePolicyError):transition_amount('confirmed','investigating',D('100'),D('80'),D('20'))
        self.assertIsNone(transition_amount('confirmed','investigating',D('100'),D('80'),D('0')))
        self.assertEqual(transition_amount('resolved','confirmed',D('100'),D('80'),D('80')),D('80'))

    def test_recovery_cannot_exceed_remaining_balance(self):
        self.assertEqual(validate_recovery('confirmed',D('80'),D('20'),'60'),D('60'))
        for amount in ('0','60.01'):
            with self.assertRaises(CasePolicyError):validate_recovery('confirmed',D('80'),D('20'),amount)
        with self.assertRaises(CasePolicyError):validate_recovery('open',None,D('0'),'1')

    def test_activity_requires_reason_and_actor(self):
        for value in ('',None,'   '):
            with self.assertRaises(CasePolicyError):required_text(value,'Author')
        self.assertEqual(required_text(' Felix ','Author'),'Felix')
