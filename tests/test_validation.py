import csv
import io
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from marginguard.validation import CONTRACTS, MAX_BYTES, parse_bundle, validate_context

ROOT = Path(__file__).resolve().parents[1]

def uploads(folder='valid'):
    return [(p.name, p.read_bytes()) for p in sorted((ROOT/'data/import_examples'/folder).glob('*.csv'))]

def context():
    return {'customers':[{'customer_id':'C001'},{'customer_id':'C002'}],
            'products':[{'product_id':f'P{i:03}','sku':f'SKU{i}'} for i in (1,2,3)]}

def change(items, dataset, row, field, value):
    result = []
    for name, content in items:
        if name == dataset+'.csv':
            rows=list(csv.DictReader(io.StringIO(content.decode('utf-8'))))
            rows[row][field]=value
            out=io.StringIO(newline=''); w=csv.DictWriter(out,fieldnames=list(rows[0])); w.writeheader();w.writerows(rows)
            content=out.getvalue().encode()
        result.append((name,content))
    return result

class CSVValidation(unittest.TestCase):
    def validate(self, items, existing=None):
        return validate_context(parse_bundle(items, 'demo-distributor'),context() if existing is None else existing,set())

    def test_valid_split_bundle_and_exact_preview(self):
        report=self.validate(uploads())
        self.assertTrue(report.ok,report.issues)
        self.assertEqual(len(report.preview),2)
        self.assertEqual(sum(Decimal(x['potential_loss']) for x in report.preview),Decimal('70.00'))

    def test_invalid_fixture_has_three_relational_errors(self):
        report=self.validate(uploads('invalid'))
        self.assertEqual({x.code for x in report.issues},{'unknown_product','date_order','overbilled_quantity'})

    def test_rejects_nan_infinity_negative_and_overprecision(self):
        for value in ['NaN','Infinity','-1','1.00001','1e2','10000000000','1,000','$10','']:
            with self.subTest(value=value):
                self.assertFalse(self.validate(change(uploads(),'invoice_lines',0,'invoiced_net_unit_price',value)).ok)

    def test_rejects_fractional_zero_and_large_quantity(self):
        for value in ['1.5','0','-1','2147483648']:
            with self.subTest(value=value):
                self.assertFalse(self.validate(change(uploads(),'invoice_lines',0,'quantity',value)).ok)

    def test_header_shape_empty_and_encoding(self):
        for content in [b'',b'order_id,order_id\nx,x\n',b'wrong\nx\n',b'order_id,customer_id,order_date,status\n',b'\xff\xfe']:
            with self.subTest(content=content):
                self.assertFalse(parse_bundle([('orders.csv',content)],'demo-distributor').ok)

    def test_unknown_columns_not_silently_dropped(self):
        content=b'order_id,customer_id,order_date,status,extra\nX,C001,2026-01-01,fulfilled,1\n'
        report=parse_bundle([('orders.csv',content)],'demo-distributor')
        self.assertEqual(report.issues[0].code,'columns')

    def test_bad_row_shape(self):
        report=parse_bundle([('orders.csv',b'order_id,customer_id,order_date,status\nX,C001,2026-01-01,fulfilled,extra\n')],'demo-distributor')
        self.assertIn('row_shape',{x.code for x in report.issues})

    def test_cross_tenant_column_rejected(self):
        content=b'tenant_id,customer_id,name,payment_terms_days\nother,C3,Test,30\n'
        self.assertIn('tenant_mismatch',{x.code for x in parse_bundle([('customers.csv',content)],'demo-distributor').issues})

    def test_duplicate_ids_file_and_database(self):
        values=change(uploads(),'orders',1,'order_id','IMP-O001')
        self.assertIn('duplicate_key',{x.code for x in self.validate(values).issues})
        report=parse_bundle(uploads(),'demo-distributor')
        validate_context(report,context(),{report.files[0].sha256})
        self.assertIn('duplicate_file',{x.code for x in report.issues})
        existing=context();existing['orders']=[{'order_id':'IMP-O001','customer_id':'C001','order_date':date(2026,9,1),'status':'fulfilled'}]
        self.assertIn('existing_key',{x.code for x in self.validate(uploads(),existing).issues})

    def test_same_order_required(self):
        report=self.validate(change(uploads(),'invoice_lines',0,'order_id','IMP-O002'))
        self.assertIn('order_mismatch',{x.code for x in report.issues})

    def test_earlier_invoice_date_and_cancellation(self):
        self.assertIn('date_order',{x.code for x in self.validate(change(uploads(),'invoices',0,'invoice_date','2026-01-01')).issues})
        self.assertIn('cancelled_order',{x.code for x in self.validate(change(uploads(),'orders',0,'status','cancelled')).issues})

    def test_existing_partial_billing_counts_towards_quantity(self):
        existing=context()
        existing['invoices']=[{'invoice_id':'PREV','order_id':'IMP-O001','invoice_date':date(2026,9,3),'status':'posted'}]
        existing['invoice_lines']=[{'invoice_line_id':'PREV-L','invoice_id':'PREV','order_id':'IMP-O001','order_line_id':'IMP-OL002','quantity':1,'invoiced_net_unit_price':Decimal('25')}]
        self.assertIn('overbilled_quantity',{x.code for x in self.validate(uploads(),existing).issues})

    def test_void_invoice_has_no_exposure_and_no_billed_quantity(self):
        report=self.validate(change(uploads(),'invoices',0,'status','void'))
        self.assertTrue(report.ok,report.issues)
        self.assertEqual(sum(Decimal(x['potential_loss']) for x in report.preview),Decimal('50'))

    def test_utf8_bom_and_leading_zero_id_preserved(self):
        report=parse_bundle([('customers.csv',b'\xef\xbb\xbfcustomer_id,name,payment_terms_days\n00001,Demo,30\n')],'demo-distributor')
        self.assertTrue(report.ok)
        self.assertEqual(report.files[0].rows[0]['customer_id'],'00001')

    def test_unsupported_filename_and_size_limit(self):
        self.assertEqual(parse_bundle([('unknown.csv',b'x')],'demo-distributor').issues[0].code,'filename')
        self.assertEqual(parse_bundle([('orders.csv',b'x'*(MAX_BYTES+1))],'demo-distributor').issues[0].code,'size')

    def test_type_order_is_independent_of_upload_order(self):
        self.assertTrue(self.validate(list(reversed(uploads()))).ok)

    def test_dates_are_strict_and_duplicate_dataset_is_blocked(self):
        self.assertFalse(self.validate(change(uploads(),'orders',0,'order_date','2026-02-30')).ok)
        self.assertFalse(self.validate(change(uploads(),'orders',0,'order_date','09/01/2026')).ok)
        self.assertIn('duplicate_dataset',{x.code for x in parse_bundle(uploads()+[uploads()[0]],'demo-distributor').issues})

    def test_duplicate_sku(self):
        values=[('products.csv',b'product_id,sku,category,standard_cost,list_price\nP4,SKU1,Tools,10,20\n')]
        self.assertIn('duplicate_sku',{x.code for x in self.validate(values).issues})

    def test_unknown_references_are_blocked(self):
        for dataset,field,value,code in [('orders','customer_id','X','unknown_customer'),('order_lines','order_id','X','unknown_order'),('invoice_lines','invoice_id','X','unknown_invoice'),('invoice_lines','order_line_id','X','unknown_order_line')]:
            with self.subTest(field=field):
                self.assertIn(code,{x.code for x in self.validate(change(uploads(),dataset,0,field,value)).issues})
