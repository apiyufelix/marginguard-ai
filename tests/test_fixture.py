import csv
import json
import unittest
from decimal import Decimal
from pathlib import Path
from marginguard.rules import underbilling

class SyntheticFixture(unittest.TestCase):
    def test_relationships_and_truth(self):
        root=Path('data/synthetic')
        def read(name):
            with (root/f'{name}.csv').open(newline='') as f:
                return list(csv.DictReader(f))
        orders={x['order_id']:x for x in read('orders')}
        lines={x['order_line_id']:x for x in read('order_lines')}
        invoices={x['invoice_id']:x for x in read('invoices')}
        truth={x['invoice_line_id']:x for x in read('ground_truth')}
        totals={}; flagged=0; loss=Decimal('0')
        for il in read('invoice_lines'):
            ol=lines[il['order_line_id']]
            self.assertIn(ol['order_id'],orders)
            self.assertEqual(invoices[il['invoice_id']]['order_id'],ol['order_id'])
            self.assertEqual(il['order_id'],ol['order_id'])
            self.assertEqual(il['tenant_id'],ol['tenant_id'])
            totals[ol['order_line_id']]=totals.get(ol['order_line_id'],0)+int(il['quantity'])
            amount=underbilling(il['quantity'],ol['agreed_net_unit_price'],il['invoiced_net_unit_price'])
            self.assertEqual(amount,Decimal(truth[il['invoice_line_id']]['expected_underbilling']))
            flagged+=amount>0; loss+=amount
        for key,qty in totals.items(): self.assertEqual(qty,int(lines[key]['quantity']))
        manifest=json.loads((root/'manifest.json').read_text())
        self.assertEqual(flagged,manifest['underbilling_cases'])
        self.assertEqual(loss,Decimal(manifest['expected_potential_loss']))
