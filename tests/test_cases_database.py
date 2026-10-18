"""Optional PostgreSQL workflow tests. Uses an isolated random schema."""
import os
from pathlib import Path
from decimal import Decimal as D
import unittest
from uuid import uuid4

URL=os.getenv('MARGINGUARD_TEST_DATABASE_URL')
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(URL,'Set MARGINGUARD_TEST_DATABASE_URL for PostgreSQL integration tests.')
class CaseDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine,event,text
        from sqlalchemy.pool import NullPool
        cls.admin=create_engine(URL,poolclass=NullPool,connect_args={'prepare_threshold':None})
        cls.schema='mg_cases_'+uuid4().hex
        with cls.admin.begin() as conn:conn.exec_driver_sql(f'CREATE SCHEMA {cls.schema}')
        cls.engine=create_engine(URL,poolclass=NullPool,connect_args={'prepare_threshold':None})
        @event.listens_for(cls.engine,'connect')
        def use_schema(dbapi,record):
            dbapi.autocommit=True
            dbapi.execute(f'SET search_path TO {cls.schema}')
            dbapi.autocommit=False
        with cls.engine.connect() as conn:
            assert conn.execute(text('SELECT current_schema()')).scalar_one()==cls.schema
            conn.connection.driver_connection.execute((ROOT/'sql/001_initial.sql').read_text(),prepare=False)
            conn.commit()
        with cls.engine.begin() as conn:
            for name in ('002_import_lineage.sql','003_investigations.sql'):
                conn.connection.driver_connection.execute((ROOT/'sql'/name).read_text(),prepare=False)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        with cls.admin.begin() as conn:conn.exec_driver_sql(f'DROP SCHEMA {cls.schema} CASCADE')
        cls.admin.dispose()

    def setUp(self):
        from sqlalchemy import text
        from marginguard.cases import run_detection,list_cases
        self.tenant='case-test-'+uuid4().hex
        with self.engine.begin() as conn:
            statements=[
              "INSERT INTO tenants VALUES(:t,'Fictional','USD')",
              "INSERT INTO customers(tenant_id,customer_id,name,payment_terms_days) VALUES(:t,'C1','Demo customer',30)",
              "INSERT INTO products(tenant_id,product_id,sku,category,standard_cost,list_price) VALUES(:t,'P1','SKU1','Tools',10,20)",
              "INSERT INTO orders(tenant_id,order_id,customer_id,order_date,status) VALUES(:t,'O1','C1','2026-01-01','fulfilled')",
              "INSERT INTO order_lines(tenant_id,order_line_id,order_id,product_id,quantity,agreed_net_unit_price,unit_cost_snapshot) VALUES(:t,'OL1','O1','P1',10,20,10)",
              "INSERT INTO invoices(tenant_id,invoice_id,order_id,invoice_date,status) VALUES(:t,'I1','O1','2026-01-02','posted')",
              "INSERT INTO invoice_lines(tenant_id,invoice_line_id,invoice_id,order_id,order_line_id,quantity,invoiced_net_unit_price) VALUES(:t,'IL1','I1','O1','OL1',10,18)",
            ]
            for sql in statements:conn.execute(text(sql),{'t':self.tenant})
        self.assertEqual(run_detection(self.engine,self.tenant)['created'],1)
        with self.engine.connect() as conn:self.finding=list_cases(conn,self.tenant)[0]['finding_id']

    def case(self):
        from marginguard.cases import get_case
        with self.engine.connect() as conn:return get_case(conn,self.tenant,self.finding)

    def action(self,func,*args,request=None,**kwargs):
        return func(self.engine,self.tenant,self.finding,*args,actor='Demo reviewer',
                    expected_version=self.case()['version'],request_key=request or str(uuid4()),**kwargs)

    def confirm(self):
        from marginguard.cases import change_status
        self.action(change_status,'investigating','Review started')
        self.action(change_status,'confirmed','Demo evidence verified',confirmation='20.00')

    def test_detection_is_idempotent_and_preserves_review(self):
        from marginguard.cases import run_detection,change_status
        self.action(change_status,'dismissed','Authorized pricing adjustment in demo review')
        before=self.case()
        self.assertEqual(run_detection(self.engine,self.tenant),{'candidates':1,'created':0,'already_saved':1})
        after=self.case()
        self.assertEqual((after['status'],after['version'],len(after['events'])),('dismissed',before['version'],len(before['events'])))
        self.assertEqual(after['evidence']['potential_loss'],'20.00')

    def test_dashboard_reads_candidates_and_cases_without_writes(self):
        from marginguard.analytics import dashboard_model,read_dashboard
        before=self.case()
        snapshot=read_dashboard(self.engine,self.tenant)
        model=dashboard_model(snapshot)
        self.assertEqual((model['candidate_lines'],model['saved_findings']),(1,1))
        self.assertEqual(model['potential_underbilling'],D('20.00'))
        self.assertEqual((model['customer_count'],model['product_count']),(1,1))
        self.assertEqual(snapshot['candidates'][0]['customer_id'],'C1')
        self.assertEqual(snapshot['cases'][0]['invoice_date'].isoformat(),'2026-01-02')
        after=self.case()
        self.assertEqual((after['version'],len(after['events'])),(before['version'],len(before['events'])))

    def test_dashboard_tenant_scoping_excludes_other_organizations(self):
        from sqlalchemy import text
        from marginguard.analytics import dashboard_model,read_dashboard
        other='empty-'+uuid4().hex
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO tenants VALUES(:t,'Other fictional tenant','USD')"),{'t':other})
        snapshot=read_dashboard(self.engine,other)
        self.assertEqual(snapshot['organization'],'Other fictional tenant')
        self.assertEqual((snapshot['candidates'],snapshot['cases']),([],[]))
        self.assertEqual(dashboard_model(snapshot)['potential_underbilling'],D('0.00'))
        with self.assertRaises(ValueError):read_dashboard(self.engine,"missing' OR 1=1 --")

    def test_dashboard_reversals_and_closed_outstanding_remain_separate(self):
        from marginguard.analytics import dashboard_model,read_dashboard
        from marginguard.cases import record_recovery,reverse_recovery,change_status
        self.confirm()
        receipt=self.action(record_recovery,'12.00','DEMO-DASH-A','Synthetic recovery')
        self.action(reverse_recovery,receipt['event_id'],'Synthetic correction')
        self.action(record_recovery,'7.00','DEMO-DASH-B','Corrected synthetic recovery')
        self.action(change_status,'resolved','Synthetic closure with balance',close_with_balance=True)
        model=dashboard_model(read_dashboard(self.engine,self.tenant))
        self.assertEqual((model['potential_underbilling'],model['confirmed_amount']),(D('20.00'),D('20.00')))
        self.assertEqual((model['net_recovered'],model['confirmed_outstanding']),(D('7.00'),D('13.00')))
        self.assertEqual(model['closed_outstanding'],D('13.00'))
        self.assertEqual(model['recovery_percent'],D('35.0'))
        self.assertEqual(model['priorities'],[])

    def test_dashboard_dates_use_invoice_cohort_not_case_creation(self):
        from datetime import date
        from marginguard.analytics import dashboard_model,read_dashboard
        self.confirm()
        snapshot=read_dashboard(self.engine,self.tenant)
        included=dashboard_model(snapshot,start=date(2026,1,2),end=date(2026,1,2),customer_id='C1')
        excluded=dashboard_model(snapshot,start=date(2026,1,3),end=date(2026,1,3),customer_id='C1')
        self.assertEqual((included['saved_findings'],included['confirmed_amount']),(1,D('20.00')))
        self.assertEqual((excluded['candidate_lines'],excluded['saved_findings']),(0,0))

    def test_full_review_partial_recoveries_and_resolution(self):
        from marginguard.cases import assign_owner,add_note,record_recovery,change_status,summarize,list_cases
        self.action(assign_owner,'Felix Apiyu')
        self.action(add_note,'Demo: compared order and invoice prices')
        self.confirm()
        self.action(record_recovery,'12.25','DEMO-A','Synthetic partial recovery')
        self.assertEqual(self.case()['net_recovered'],D('12.25'))
        self.action(record_recovery,'7.75','DEMO-B','Synthetic final recovery')
        self.action(change_status,'resolved','Demo fully recovered')
        case=self.case()
        self.assertEqual((case['status'],case['confirmed_amount'],case['net_recovered']),('resolved',D('20'),D('20')))
        with self.engine.connect() as conn:summary=summarize(list_cases(conn,self.tenant))
        self.assertEqual(summary['confirmed_outstanding'],0)
        self.assertEqual([x['event_type'] for x in case['events']],['created','assignment','note','status_change','status_change','recovery','recovery','status_change'])

    def test_over_recovery_and_duplicate_reference_roll_back(self):
        from marginguard.cases import record_recovery
        from marginguard.workflow import CasePolicyError
        self.confirm()
        self.action(record_recovery,'10','DEMO-A','Synthetic')
        before=self.case()
        for amount,reference in [('10.01','DEMO-B'),('1','demo-a')]:
            with self.assertRaises(CasePolicyError):self.action(record_recovery,amount,reference,'Synthetic')
        after=self.case()
        self.assertEqual((after['version'],len(after['events']),after['net_recovered']),
                         (before['version'],len(before['events']),D('10')))

    def test_replayed_request_is_not_double_counted_and_changed_payload_rejected(self):
        from marginguard.cases import record_recovery
        from marginguard.workflow import CasePolicyError
        self.confirm();version=self.case()['version'];key=str(uuid4())
        args=(self.engine,self.tenant,self.finding,'10','DEMO-A','Synthetic')
        kw={'actor':'Demo reviewer','expected_version':version,'request_key':key}
        first=record_recovery(*args,**kw);second=record_recovery(*args,**kw)
        self.assertFalse(first['replayed']);self.assertTrue(second['replayed'])
        self.assertEqual(first['event_id'],second['event_id'])
        self.assertEqual(self.case()['net_recovered'],D('10'))
        with self.assertRaises(CasePolicyError):
            record_recovery(self.engine,self.tenant,self.finding,'9','DEMO-A','Synthetic',**kw)

    def test_stale_version_is_rejected(self):
        from marginguard.cases import add_note,CaseChanged
        version=self.case()['version']
        self.action(add_note,'First edit')
        with self.assertRaises(CaseChanged):add_note(self.engine,self.tenant,self.finding,'Stale edit','Demo reviewer',version,str(uuid4()))
        self.assertEqual(len(self.case()['events']),2)

    def test_reversal_is_once_and_retains_original_event(self):
        from marginguard.cases import record_recovery,reverse_recovery,active_recoveries
        from marginguard.workflow import CasePolicyError
        self.confirm();event=self.action(record_recovery,'12','DEMO-A','Synthetic')
        self.action(reverse_recovery,event['event_id'],'Demo correction')
        self.assertEqual(self.case()['net_recovered'],0)
        self.assertEqual(len(active_recoveries(self.case())),0)
        with self.assertRaises(CasePolicyError):self.action(reverse_recovery,event['event_id'],'Second reversal')
        self.action(record_recovery,'10','DEMO-A','Corrected synthetic recovery')
        self.assertEqual(self.case()['net_recovered'],D('10'))

    def test_closing_with_balance_is_explicit_and_not_recovered(self):
        from marginguard.cases import change_status
        from marginguard.workflow import CasePolicyError
        self.confirm()
        with self.assertRaises(CasePolicyError):self.action(change_status,'resolved','Missing explicit closure choice')
        self.action(change_status,'resolved','Demo balance intentionally closed',close_with_balance=True)
        self.assertEqual(self.case()['net_recovered'],0)
        self.assertEqual(self.case()['events'][-1]['details']['unrecovered_balance_at_close'],'20.00')
        self.action(change_status,'confirmed','Demo case reopened')
        self.assertEqual(self.case()['confirmed_amount'],D('20'))

    def test_cross_tenant_case_access_is_denied(self):
        from marginguard.cases import get_case,add_note
        from marginguard.workflow import CasePolicyError
        with self.engine.connect() as conn:
            with self.assertRaises(CasePolicyError):get_case(conn,'another-tenant',self.finding)
        with self.assertRaises(CasePolicyError):add_note(self.engine,'another-tenant',self.finding,'Unauthorized','Demo reviewer',1,str(uuid4()))
        self.assertEqual(len(self.case()['events']),1)

    def test_events_cannot_be_updated_or_deleted(self):
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError
        for statement in ('UPDATE case_events SET actor=\'Changed\' WHERE tenant_id=:t','DELETE FROM case_events WHERE tenant_id=:t'):
            with self.assertRaises(DBAPIError):
                with self.engine.begin() as conn:conn.execute(text(statement),{'t':self.tenant})
        self.assertEqual(self.case()['events'][0]['actor'],'MarginGuard rule engine')

    def test_recovery_requires_confirmation_and_reopen_for_reversal(self):
        from marginguard.cases import record_recovery,change_status,reverse_recovery
        from marginguard.workflow import CasePolicyError
        with self.assertRaises(CasePolicyError):self.action(record_recovery,'1','DEMO-A','Synthetic')
        self.confirm();event=self.action(record_recovery,'20','DEMO-A','Synthetic')
        self.action(change_status,'resolved','Done')
        with self.assertRaises(CasePolicyError):self.action(reverse_recovery,event['event_id'],'Need reopen')
        self.action(change_status,'confirmed','Reopen to correct')
        self.action(reverse_recovery,event['event_id'],'Demo correction')
        self.assertEqual(self.case()['net_recovered'],0)

    def test_injected_event_failure_rolls_back_status_and_version(self):
        from sqlalchemy import event
        from marginguard.cases import change_status
        before=self.case()
        def fail(conn,cursor,statement,params,context,executemany):
            if statement.startswith('INSERT INTO case_events'):raise RuntimeError('Injected event failure')
        event.listen(self.engine,'before_cursor_execute',fail)
        try:
            with self.assertRaises(RuntimeError):self.action(change_status,'investigating','Begin review')
        finally:event.remove(self.engine,'before_cursor_execute',fail)
        after=self.case()
        self.assertEqual((after['status'],after['version'],len(after['events'])),(before['status'],before['version'],len(before['events'])))

    def test_full_fixture_detection_matches_ground_truth_with_source_lineage(self):
        import csv
        import io
        import json
        from sqlalchemy import text
        from marginguard.validation import CONTRACTS
        from marginguard.imports import commit_upload
        from marginguard.cases import run_detection,list_cases
        tenant='full-fixture-'+uuid4().hex
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO tenants VALUES(:t,'Full fictional fixture','USD')"),{'t':tenant})
        uploads=[]
        for dataset in CONTRACTS:
            with (ROOT/'data/synthetic'/f'{dataset}.csv').open(newline='') as source:
                rows=list(csv.DictReader(source))
            for row in rows:row['tenant_id']=tenant
            output=io.StringIO(newline='')
            writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            uploads.append((dataset+'.csv',output.getvalue().encode()))
        commit_upload(self.engine,tenant,uploads)
        manifest=json.loads((ROOT/'data/synthetic/manifest.json').read_text())
        result=run_detection(self.engine,tenant)
        with self.engine.connect() as conn:cases=list_cases(conn,tenant)
        self.assertEqual(result['created'],manifest['underbilling_cases'])
        self.assertEqual(sum(x['potential_loss'] for x in cases),D(manifest['expected_potential_loss']))
        self.assertTrue(all(x['evidence']['order_source_batch'] and x['evidence']['invoice_source_batch'] for x in cases))
