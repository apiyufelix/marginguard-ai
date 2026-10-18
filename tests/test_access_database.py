"""Opt-in schema constraints for the access foundation; no login enforcement yet."""
import os
from pathlib import Path
import unittest
from uuid import uuid4

URL = os.getenv('MARGINGUARD_TEST_DATABASE_URL')
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(URL, 'Set MARGINGUARD_TEST_DATABASE_URL for PostgreSQL integration tests.')
class AccessSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine, event
        from sqlalchemy.pool import NullPool
        cls.admin = create_engine(URL, poolclass=NullPool, connect_args={'prepare_threshold': None})
        cls.schema = 'mg_access_' + uuid4().hex
        with cls.admin.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA {cls.schema}')
        cls.engine = create_engine(URL, poolclass=NullPool, connect_args={'prepare_threshold': None})

        @event.listens_for(cls.engine, 'connect')
        def set_schema(dbapi_connection, connection_record):
            dbapi_connection.autocommit = True
            dbapi_connection.execute(f'SET search_path TO {cls.schema}')
            dbapi_connection.autocommit = False

        with cls.engine.connect() as conn:
            conn.connection.driver_connection.execute((ROOT/'sql/001_initial.sql').read_text(), prepare=False)
            conn.commit()
        with cls.engine.begin() as conn:
            for filename in ('002_import_lineage.sql', '003_investigations.sql'):
                conn.connection.driver_connection.execute((ROOT/'sql'/filename).read_text(), prepare=False)
            # Real pre-migration data, including an event protected by the trigger.
            conn.exec_driver_sql("INSERT INTO tenants VALUES ('legacy','Legacy','USD')")
            conn.exec_driver_sql("INSERT INTO customers VALUES ('legacy','C','Customer',30)")
            conn.exec_driver_sql("INSERT INTO products VALUES ('legacy','P','SKU','Tools',1,2)")
            conn.exec_driver_sql("INSERT INTO orders(tenant_id,order_id,customer_id,order_date,status) VALUES ('legacy','O','C',CURRENT_DATE,'fulfilled')")
            conn.exec_driver_sql("INSERT INTO order_lines(tenant_id,order_line_id,order_id,product_id,quantity,agreed_net_unit_price,unit_cost_snapshot) VALUES ('legacy','OL','O','P',1,2,1)")
            conn.exec_driver_sql("INSERT INTO invoices(tenant_id,invoice_id,order_id,invoice_date,status) VALUES ('legacy','I','O',CURRENT_DATE,'posted')")
            conn.exec_driver_sql("INSERT INTO invoice_lines(tenant_id,invoice_line_id,invoice_id,order_id,order_line_id,quantity,invoiced_net_unit_price) VALUES ('legacy','IL','I','O','OL',1,1)")
            conn.exec_driver_sql("INSERT INTO findings(tenant_id,finding_id,invoice_line_id,rule_code,rule_version,potential_loss,evidence) VALUES ('legacy','F','IL','test','1',1,'{}')")
            conn.exec_driver_sql("INSERT INTO case_events(tenant_id,event_id,finding_id,event_type,actor,details) VALUES ('legacy','E','F','note','Original label','{}')")
            conn.connection.driver_connection.execute((ROOT/'sql/004_access_foundation.sql').read_text(), prepare=False)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        with cls.admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA {cls.schema} CASCADE')
        cls.admin.dispose()

    def execute(self, sql, **params):
        from sqlalchemy import text
        # Each assertion is a standalone statement; failed constraints must not
        # leave an aborted transaction that hides subsequent assertions.
        with self.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
            return conn.execute(text(sql), params)

    def user(self, issuer='https://identity.example', subject=None, email='same@example.test'):
        user_id = uuid4()
        self.execute('INSERT INTO app_users(user_id,oidc_issuer,oidc_subject,display_name,email) VALUES (:u,:i,:s,\'Test user\',:e)',
                     u=user_id, i=issuer, s=subject or uuid4().hex, e=email)
        return user_id

    def test_identity_uses_issuer_and_subject_not_email(self):
        from sqlalchemy.exc import IntegrityError
        subject = uuid4().hex
        self.user(subject=subject)
        self.user(issuer='https://other.example', subject=subject)
        with self.assertRaises(IntegrityError):
            self.user(subject=subject)

    def test_roles_defaults_and_duplicate_memberships(self):
        from sqlalchemy.exc import IntegrityError
        user_id = self.user()
        self.execute("INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES ('legacy',:u,'viewer')", u=user_id)
        row = self.execute('SELECT role,is_active FROM tenant_memberships WHERE user_id=:u', u=user_id).one()
        self.assertEqual(tuple(row), ('viewer', True))
        with self.assertRaises(IntegrityError):
            self.execute("INSERT INTO tenant_memberships VALUES ('legacy',:u,'admin',true,now())", u=user_id)
        for role in ('analyst', 'admin'):
            self.execute('UPDATE tenant_memberships SET role=:r WHERE user_id=:u', r=role, u=user_id)
        with self.assertRaises(IntegrityError):
            self.execute("UPDATE tenant_memberships SET role='owner' WHERE user_id=:u", u=user_id)
        self.execute('UPDATE tenant_memberships SET is_active=false WHERE user_id=:u', u=user_id)
        self.assertFalse(self.execute('SELECT is_active FROM tenant_memberships WHERE user_id=:u', u=user_id).scalar_one())

    def test_memberships_require_existing_user_and_company(self):
        from sqlalchemy.exc import IntegrityError
        with self.assertRaises(IntegrityError):
            self.execute("INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES ('legacy',:u,'viewer')", u=uuid4())
        with self.assertRaises(IntegrityError):
            self.execute("INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (:t,:u,'viewer')", t=uuid4().hex, u=self.user())

    def test_event_actor_requires_membership_in_same_company(self):
        from sqlalchemy.exc import IntegrityError
        user_id = self.user()
        other = uuid4().hex
        self.execute("INSERT INTO tenants VALUES (:t,'Other','USD')", t=other)
        self.execute("INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (:t,:u,'analyst')", t=other, u=user_id)
        sql = "INSERT INTO case_events(tenant_id,event_id,finding_id,event_type,actor,details,actor_user_id) VALUES ('legacy',:e,'F','note','Test user','{}',:u)"
        with self.assertRaises(IntegrityError):
            self.execute(sql, e=uuid4().hex, u=user_id)
        self.execute("INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES ('legacy',:u,'analyst')", u=user_id)
        self.execute(sql, e=uuid4().hex, u=user_id)
        with self.assertRaises(IntegrityError):
            self.execute("DELETE FROM tenant_memberships WHERE tenant_id='legacy' AND user_id=:u", u=user_id)

    def test_legacy_event_preserved_and_append_only(self):
        from sqlalchemy.exc import DBAPIError
        row = self.execute("SELECT actor,actor_user_id FROM case_events WHERE tenant_id='legacy' AND event_id='E'").one()
        self.assertEqual(tuple(row), ('Original label', None))
        self.assertEqual(self.execute("SELECT count(*) FROM schema_migrations WHERE version='004'").scalar_one(), 1)
        with self.assertRaises(DBAPIError):
            self.execute("UPDATE case_events SET actor='Changed' WHERE tenant_id='legacy' AND event_id='E'")
