"""Authorization integration tests reuse the existing isolated case fixture."""
import os
import time
import unittest
from uuid import uuid4
from pathlib import Path
from unittest.mock import patch
import test_cases_database as fixtures
from marginguard.access import (AccessDenied, CompanyEngine, Identity, google_identity,
    register_identity, companies, set_membership, membership_list)


class GoogleClaims(unittest.TestCase):
    def claims(self, **overrides):
        class Claims(dict):
            is_logged_in = True
        return Claims(iss='https://accounts.google.com',sub='stable-id',name='Reviewer',
                      email='reviewer@example.test',exp=time.time()+3600,**overrides)

    def test_verified_claims_and_email_is_not_identity(self):
        c = self.claims()
        first = google_identity(c)
        c['email'] = 'changed@example.test'
        second = google_identity(c)
        self.assertEqual((first.issuer,first.subject),(second.issuer,second.subject))

    def test_expired_or_missing_expiry_denied(self):
        for expiry in (None,True,0,time.time()-1,float('nan')):
            c = self.claims(); c['exp'] = expiry
            with self.assertRaises(AccessDenied): google_identity(c)

    def test_missing_subject_or_other_provider_denied(self):
        for field,value in (('sub',''),('sub',None),('iss','https://untrusted.example')):
            c = self.claims(); c[field] = value
            with self.assertRaises(AccessDenied): google_identity(c)

    def test_signed_out_denied(self):
        c = self.claims(); c.is_logged_in = False
        with self.assertRaises(AccessDenied): google_identity(c)


@unittest.skipUnless(os.getenv('MARGINGUARD_TEST_DATABASE_URL'),'Set MARGINGUARD_TEST_DATABASE_URL for PostgreSQL integration tests.')
class CompanyAuthorization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.CaseDatabase.setUpClass.__func__(cls)
        with cls.engine.begin() as conn:
            for name in ('004_access_foundation.sql','005_membership_audit.sql'):
                conn.connection.driver_connection.execute((Path(__file__).resolve().parents[1]/'sql'/name).read_text(),prepare=False)

    @classmethod
    def tearDownClass(cls):
        fixtures.CaseDatabase.tearDownClass.__func__(cls)

    def setUp(self):
        fixtures.CaseDatabase.setUp(self)
        self.identity = Identity('https://accounts.google.com',uuid4().hex,'Verified reviewer','same@example.test',time.time()+3600)
        self.user = register_identity(self.engine,self.identity)['user_id']

    case = fixtures.CaseDatabase.case

    def execute(self, sql, **params):
        from sqlalchemy import text
        with self.engine.begin() as conn:
            return conn.execute(text(sql),params)

    def scoped(self, user=None, tenant=None, expires=None):
        return CompanyEngine(self.engine,user or self.user,tenant or self.tenant,expires or time.time()+3600)

    def grant(self, role='viewer', user=None):
        self.execute('''INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (:t,:u,:r)
            ON CONFLICT(tenant_id,user_id) DO UPDATE SET role=EXCLUDED.role,is_active=true''',
            t=self.tenant,u=user or self.user,r=role)

    def test_signin_has_no_access_and_does_not_auto_link_email(self):
        from marginguard.analytics import read_dashboard
        self.assertEqual(companies(self.engine,self.user),[])
        with self.assertRaises(AccessDenied): read_dashboard(self.scoped(),self.tenant)
        self.grant('admin')
        other = register_identity(self.engine,Identity(self.identity.issuer,uuid4().hex,'Other',self.identity.email,time.time()+3600))
        self.assertNotEqual(other['user_id'],self.user)
        self.assertEqual(companies(self.engine,other['user_id']),[])
        self.assertEqual(register_identity(self.engine,self.identity)['user_id'],self.user)

    def test_viewer_reads_but_every_write_path_and_admin_denied(self):
        from marginguard.analytics import read_dashboard
        from marginguard.cases import run_detection,add_note,assign_owner,change_status,record_recovery,reverse_recovery
        from marginguard.imports import validate_upload,commit_upload
        self.grant()
        e = self.scoped()
        self.assertEqual(len(read_dashboard(e,self.tenant)['cases']),1)
        with e.connect() as conn:
            with self.assertRaises(AccessDenied): validate_upload(conn,self.tenant,[])
        calls = [lambda:run_detection(e,self.tenant),lambda:commit_upload(e,self.tenant,[]),
                 lambda:membership_list(e,self.tenant),
                 lambda:add_note(e,self.tenant,self.finding,'Note','Forged',1,str(uuid4())),
                 lambda:assign_owner(e,self.tenant,self.finding,'Owner','Forged',1,str(uuid4())),
                 lambda:change_status(e,self.tenant,self.finding,'investigating','Reason','Forged',1,str(uuid4())),
                 lambda:record_recovery(e,self.tenant,self.finding,'1','R','Note','Forged',1,str(uuid4())),
                 lambda:reverse_recovery(e,self.tenant,self.finding,'missing','Reason','Forged',1,str(uuid4())),
                 lambda:set_membership(e,self.tenant,self.user,'admin',True)]
        for call in calls:
            with self.assertRaises(AccessDenied): call()
        self.assertEqual(self.case()['version'],1)

    def test_cross_company_reads_and_writes_denied(self):
        from marginguard.cases import list_cases,run_detection,get_case
        from marginguard.analytics import read_dashboard
        self.grant('admin')
        other = 'other-'+uuid4().hex
        with self.scoped().connect() as conn:
            with self.assertRaises(AccessDenied): list_cases(conn,other)
            with self.assertRaises(AccessDenied): get_case(conn,other,self.finding)
        with self.assertRaises(AccessDenied): read_dashboard(self.scoped(),other)
        with self.assertRaises(AccessDenied): run_detection(self.scoped(),other)

    def test_analyst_writes_verified_actor_and_cannot_administer(self):
        from marginguard.cases import add_note,run_detection
        self.grant('analyst')
        e = self.scoped()
        result = add_note(e,self.tenant,self.finding,'Checked','Forged author',1,str(uuid4()))
        event = next(x for x in self.case()['events'] if x['event_id']==result['event_id'])
        self.assertEqual((event['actor'],event['actor_user_id']),('Verified reviewer',self.user))
        from marginguard.reporting import case_payload
        exported = case_payload(self.case())
        saved = next(x for x in exported['case_activity'] if x['event_id']==result['event_id'])
        self.assertEqual(saved['actor_user_id'],str(self.user))
        self.assertEqual(run_detection(e,self.tenant)['created'],0)
        with self.assertRaises(AccessDenied): membership_list(e,self.tenant)

    def test_revocation_disabled_user_and_expiry_rechecked(self):
        from marginguard.analytics import read_dashboard
        from marginguard.cases import add_note
        self.grant('analyst'); e = self.scoped()
        read_dashboard(e,self.tenant)
        self.execute('UPDATE tenant_memberships SET is_active=false WHERE tenant_id=:t AND user_id=:u',t=self.tenant,u=self.user)
        with self.assertRaises(AccessDenied): add_note(e,self.tenant,self.finding,'Note','Author',1,str(uuid4()))
        self.grant('analyst')
        with self.assertRaises(AccessDenied): read_dashboard(self.scoped(expires=time.time()-1),self.tenant)
        self.execute('UPDATE app_users SET is_active=false WHERE user_id=:u',u=self.user)
        with self.assertRaises(AccessDenied): read_dashboard(e,self.tenant)
        with self.assertRaises(AccessDenied): register_identity(self.engine,self.identity)
        self.assertEqual(companies(self.engine,self.user),[])

    def test_admin_bootstrap_audit_and_last_admin_protection(self):
        set_membership(self.engine,self.tenant,self.user,'admin',True,bootstrap=True)
        e = self.scoped()
        with self.assertRaises(AccessDenied): set_membership(self.engine,self.tenant,self.user,'admin',True,bootstrap=True)
        for role,active in (('viewer',True),('admin',False)):
            with self.assertRaises(AccessDenied): set_membership(e,self.tenant,self.user,role,active)
        self.assertEqual(membership_list(e,self.tenant)[0]['role'],'admin')
        second = register_identity(self.engine,Identity(self.identity.issuer,uuid4().hex,'Second',None,time.time()+3600))['user_id']
        set_membership(e,self.tenant,second,'admin',True)
        set_membership(e,self.tenant,self.user,'viewer',True)
        self.assertEqual(self.execute('SELECT count(*) FROM membership_events WHERE tenant_id=:t',t=self.tenant).scalar_one(),3)
        with self.assertRaises(AccessDenied): membership_list(e,self.tenant)

    def test_scoped_connection_context_does_not_escape(self):
        from marginguard.access import KEY,require_access
        self.grant('analyst')
        with self.scoped().connect() as conn:
            require_access(conn,self.tenant)
            info = conn.info
            self.assertIn(KEY,info)
        self.assertNotIn(KEY,info)
        self.assertNotIn('marginguard_actor',info)

    def test_analyst_can_import_and_detection_records_actor(self):
        from marginguard.imports import commit_upload
        from marginguard.cases import run_detection
        self.grant('analyst')
        # Existing customer/product IDs for the real import fixture.
        self.execute("INSERT INTO customers(tenant_id,customer_id,name,payment_terms_days) VALUES (:t,'C001','Customer',30),(:t,'C002','Customer 2',30)",t=self.tenant)
        for product in ('P001','P002','P003'):
            self.execute("INSERT INTO products(tenant_id,product_id,sku,category,standard_cost,list_price) VALUES (:t,:p,:p,'Tools',10,20)",t=self.tenant,p=product)
        root = Path(__file__).resolve().parents[1]
        uploads = [(p.name,p.read_bytes()) for p in sorted((root/'data/import_examples/valid').glob('*.csv'))]
        self.assertEqual(sum(x['rows'] for x in commit_upload(self.scoped(),self.tenant,uploads)),11)
        self.assertEqual(run_detection(self.scoped(),self.tenant)['created'],2)
        rows = self.execute("SELECT actor,actor_user_id FROM case_events WHERE tenant_id=:t AND actor_user_id IS NOT NULL",t=self.tenant).all()
        self.assertEqual(len(rows),2)
        self.assertTrue(all(tuple(r)==('Verified reviewer',self.user) for r in rows))
