"""Opt-in integration tests: use a disposable PostgreSQL database, never production.

Set MARGINGUARD_TEST_DATABASE_URL to run these. An isolated random schema is
created and dropped; existing public tables are never used for test writes.
"""
import os
from pathlib import Path
import unittest
from uuid import uuid4

URL = os.getenv('MARGINGUARD_TEST_DATABASE_URL')
ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(URL, 'Set MARGINGUARD_TEST_DATABASE_URL for PostgreSQL integration tests.')
class DatabaseImports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine, event
        from sqlalchemy.pool import NullPool
        cls.admin = create_engine(URL,poolclass=NullPool,connect_args={'prepare_threshold':None})
        cls.schema = 'mg_test_'+uuid4().hex
        with cls.admin.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA {cls.schema}')
        cls.engine = create_engine(URL,connect_args={'prepare_threshold':None},poolclass=NullPool)
        @event.listens_for(cls.engine, 'connect')
        def use_test_schema(dbapi_connection, connection_record):
            dbapi_connection.autocommit = True
            dbapi_connection.execute(f'SET search_path TO {cls.schema}')
            dbapi_connection.autocommit = False
        with cls.engine.connect() as conn:
            from sqlalchemy import text
            assert conn.execute(text('SELECT current_schema()')).scalar_one() == cls.schema
            conn.connection.driver_connection.execute((ROOT/'sql/001_initial.sql').read_text(),prepare=False)
            conn.commit()
        with cls.engine.begin() as conn:
            conn.connection.driver_connection.execute((ROOT/'sql/002_import_lineage.sql').read_text(),prepare=False)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        with cls.admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA {cls.schema} CASCADE')
        cls.admin.dispose()

    def setUp(self):
        from sqlalchemy import text
        self.tenant = 'test-'+uuid4().hex
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO tenants VALUES(:t,'Test tenant','USD')"),{'t':self.tenant})
            conn.execute(text('INSERT INTO customers(tenant_id,customer_id,name,payment_terms_days) VALUES(:t,:id,:name,30)'),[{'t':self.tenant,'id':f'C{i:03}','name':f'Customer {i}'} for i in (1,2)])
            conn.execute(text("INSERT INTO products(tenant_id,product_id,sku,category,standard_cost,list_price) VALUES(:t,:id,:id,'Tools',10,20)"),[{'t':self.tenant,'id':f'P{i:03}'} for i in (1,2,3)])

    def inputs(self,folder='valid'):
        return [(p.name,p.read_bytes()) for p in sorted((ROOT/'data/import_examples'/folder).glob('*.csv'))]

    def counts(self):
        from sqlalchemy import text
        with self.engine.connect() as conn:
            return {name:conn.execute(text(f'SELECT count(*) FROM {name} WHERE tenant_id=:t'),{'t':self.tenant}).scalar_one() for name in ('orders','order_lines','invoices','invoice_lines','import_batches','import_rows')}

    def test_atomic_import_lineage_and_duplicate_rejection(self):
        from decimal import Decimal
        from sqlalchemy import text
        from marginguard.imports import commit_upload,ImportRejected
        receipt=commit_upload(self.engine,self.tenant,list(reversed(self.inputs())))
        self.assertEqual(sum(x['rows'] for x in receipt),11)
        expected={'orders':2,'order_lines':3,'invoices':2,'invoice_lines':4,'import_batches':4,'import_rows':11}
        self.assertEqual(self.counts(),expected)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text('SELECT sum(potential_loss) FROM underbilling_candidates WHERE tenant_id=:t'),{'t':self.tenant}).scalar_one(),Decimal('70'))
            self.assertEqual(conn.execute(text("SELECT count(*) FROM import_batches WHERE tenant_id=:t AND status='committed'"),{'t':self.tenant}).scalar_one(),4)
            self.assertEqual(conn.execute(text('SELECT count(*) FROM invoice_lines il JOIN import_rows ir ON il.tenant_id=ir.tenant_id AND il.import_batch_id=ir.batch_id AND il.source_row=ir.row_number WHERE il.tenant_id=:t'),{'t':self.tenant}).scalar_one(),4)
        with self.assertRaises(ImportRejected): commit_upload(self.engine,self.tenant,self.inputs())
        self.assertEqual(self.counts(),expected)

    def test_invalid_bundle_does_not_write(self):
        from marginguard.imports import commit_upload,ImportRejected
        before=self.counts()
        with self.assertRaises(ImportRejected): commit_upload(self.engine,self.tenant,self.inputs('invalid'))
        self.assertEqual(self.counts(),before)

    def test_failure_after_some_inserts_rolls_back_everything(self):
        from sqlalchemy import event
        from marginguard.imports import commit_upload
        before=self.counts()
        def break_invoice(conn,cursor,statement,parameters,context,executemany):
            if statement.startswith('INSERT INTO invoices '):
                raise RuntimeError('Injected write failure after orders and lines were inserted.')
        event.listen(self.engine,'before_cursor_execute',break_invoice)
        try:
            with self.assertRaises(RuntimeError): commit_upload(self.engine,self.tenant,self.inputs())
        finally:
            event.remove(self.engine,'before_cursor_execute',break_invoice)
        self.assertEqual(self.counts(),before)

    def test_revalidation_sees_new_database_conflicts(self):
        from marginguard.imports import commit_upload,ImportRejected,validate_upload
        from sqlalchemy import text
        with self.engine.connect() as conn:
            self.assertTrue(validate_upload(conn,self.tenant,self.inputs()).ok)
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO orders(tenant_id,order_id,customer_id,order_date,status) VALUES(:t,'IMP-O001','C001','2026-09-01','fulfilled')"),{'t':self.tenant})
        before=self.counts()
        with self.assertRaises(ImportRejected): commit_upload(self.engine,self.tenant,self.inputs())
        self.assertEqual(self.counts(),before)

    def test_cross_tenant_sources_do_not_leak(self):
        from marginguard.imports import validate_upload
        items=[('orders.csv',b'order_id,customer_id,order_date,status\nONLY-HERE,ONLY-ELSEWHERE,2026-09-01,fulfilled\n')]
        from sqlalchemy import text
        other='other-'+uuid4().hex
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO tenants VALUES(:t,'Other tenant','USD')"),{'t':other})
            conn.execute(text("INSERT INTO customers(tenant_id,customer_id,name,payment_terms_days) VALUES(:t,'ONLY-ELSEWHERE','Other customer',30)"),{'t':other})
        with self.engine.connect() as conn:
            report=validate_upload(conn,self.tenant,items)
        self.assertIn('unknown_customer',{x.code for x in report.issues})
