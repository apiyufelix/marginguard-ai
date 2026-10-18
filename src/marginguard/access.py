"""App authorization; raw engines remain trusted local maintenance interfaces.

The web app binds each connection to a user/company with CompanyEngine. Service
entry points call require_access inside their own transaction. No role is cached.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import time
from uuid import UUID, uuid4
import json

from sqlalchemy import text

KEY = 'marginguard_access'
ROLES = {'viewer': frozenset({'read'}), 'analyst': frozenset({'read','write'}),
         'admin': frozenset({'read','write','admin'})}


class AccessDenied(ValueError):
    pass


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str
    name: str
    email: str | None
    expires: float


def google_identity(claims, now=None):
    """Consume only identity claims already verified by Streamlit's OIDC flow."""
    if not getattr(claims, 'is_logged_in', False):
        raise AccessDenied('Sign in to continue.')
    if claims.get('iss') not in ('https://accounts.google.com','accounts.google.com'):
        raise AccessDenied('This sign-in provider is not supported.')
    subject = claims.get('sub')
    expiry = claims.get('exp')
    if not isinstance(subject,str) or not subject.strip():
        raise AccessDenied('Your sign-in identity is incomplete. Sign out and sign in again.')
    if isinstance(expiry,bool) or not isinstance(expiry,(int,float)) or not expiry > (time.time() if now is None else now):
        raise AccessDenied('Your sign-in expired. Sign out and sign in again.')
    name = str(claims.get('name') or 'Google user').strip()[:128] or 'Google user'
    email = claims.get('email') if isinstance(claims.get('email'),str) else None
    return Identity('https://accounts.google.com',subject,name,email,expiry)


def register_identity(engine, identity):
    """Create an account with NO memberships. Never reactivate a disabled user."""
    if identity.expires <= time.time():
        raise AccessDenied('Your sign-in expired. Sign out and sign in again.')
    with engine.begin() as conn:
        row = conn.execute(text('''INSERT INTO app_users
            (user_id,oidc_issuer,oidc_subject,display_name,email)
            VALUES (:u,:i,:s,:n,:e)
            ON CONFLICT(oidc_issuer,oidc_subject) DO UPDATE
            SET display_name=EXCLUDED.display_name,email=EXCLUDED.email
            RETURNING user_id,display_name,is_active'''),
            {'u':uuid4(),'i':identity.issuer,'s':identity.subject,'n':identity.name,'e':identity.email}).mappings().one()
    if not row['is_active']:
        raise AccessDenied('Your MarginGuard account is inactive. Contact your company administrator.')
    return dict(row)


def companies(engine, user_id):
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text('''SELECT m.tenant_id,t.name,m.role
            FROM tenant_memberships m JOIN tenants t USING(tenant_id)
            JOIN app_users u USING(user_id)
            WHERE m.user_id=:u AND m.is_active AND u.is_active ORDER BY t.name,m.tenant_id'''), {'u':user_id}).mappings()]


@dataclass(frozen=True)
class AccessContext:
    user_id: UUID
    tenant: str
    expires: float


class CompanyEngine:
    """Connection scope for the web UI; not a SQL sandbox or a public API."""
    def __init__(self, engine, user_id, tenant, expires):
        self.engine = engine
        self.context = AccessContext(user_id,tenant,expires)

    @contextmanager
    def _scope(self, transaction):
        manager = self.engine.begin() if transaction else self.engine.connect()
        with manager as conn:
            if KEY in conn.info:
                raise RuntimeError('An authorization context is already attached.')
            conn.info[KEY] = self.context
            try:
                yield conn
            finally:
                conn.info.pop(KEY,None)
                conn.info.pop('marginguard_actor',None)

    def begin(self):
        return self._scope(True)

    def connect(self):
        return self._scope(False)


def require_access(conn, tenant, permission='read'):
    context = conn.info.get(KEY)
    if context is None:
        # Trusted scripts/tests using DATABASE_URL keep their maintenance access.
        return None
    if context.tenant != tenant or context.expires <= time.time():
        raise AccessDenied('Company access denied or sign-in expired. Refresh and sign in again.')
    lock = ' FOR SHARE OF m,u' if permission != 'read' else ''
    row = conn.execute(text('''SELECT u.user_id,u.display_name,m.role
        FROM tenant_memberships m JOIN app_users u USING(user_id)
        WHERE m.tenant_id=:t AND m.user_id=:u AND m.is_active AND u.is_active''' + lock),
        {'t':tenant,'u':context.user_id}).mappings().first()
    if row is None or permission not in ROLES.get(row['role'],frozenset()):
        raise AccessDenied('Your current company role does not permit this action.')
    conn.info['marginguard_actor'] = dict(row)
    return dict(row)


def membership_list(engine, tenant):
    with engine.connect() as conn:
        if require_access(conn,tenant,'admin') is None:
            raise AccessDenied('An authenticated company administrator is required.')
        return [dict(r) for r in conn.execute(text('''SELECT u.user_id,u.display_name,u.email,
            u.is_active AS account_active,m.role,m.is_active
            FROM tenant_memberships m JOIN app_users u USING(user_id)
            WHERE m.tenant_id=:t ORDER BY u.display_name,u.user_id'''),{'t':tenant}).mappings()]


def _membership_audit(conn, tenant, actor, target, before, after, kind):
    conn.execute(text('''INSERT INTO membership_events
        (event_id,tenant_id,actor_user_id,target_user_id,event_type,details)
        VALUES(:e,:t,:a,:u,:k,CAST(:d AS jsonb))'''),
        {'e':uuid4(),'t':tenant,'a':actor,'u':target,'k':kind,
         'd':json.dumps({'before':before,'after':after},default=str)})


def set_membership(engine, tenant, target_user_id, role, active, *, bootstrap=False):
    if role not in ROLES or not isinstance(active,bool):
        raise ValueError('Choose a valid role and active state.')
    target_user_id = UUID(str(target_user_id))
    with engine.begin() as conn:
        # Serialize membership changes, including concurrent last-admin demotions.
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {'key':'membership:'+tenant})
        if bootstrap:
            if isinstance(engine,CompanyEngine) or role != 'admin' or not active:
                raise AccessDenied('Bootstrap requires a trusted local maintenance connection.')
            exists = conn.execute(text("SELECT 1 FROM tenant_memberships WHERE tenant_id=:t AND role='admin' LIMIT 1"),{'t':tenant}).first()
            if exists:
                raise AccessDenied('This company already has an admin membership. Use its administrator.')
            actor_id = target_user_id
        else:
            actor = require_access(conn,tenant,'admin')
            if actor is None:
                raise AccessDenied('An authenticated company administrator is required.')
            actor_id = actor['user_id']
        target = conn.execute(text('SELECT is_active FROM app_users WHERE user_id=:u FOR SHARE'),{'u':target_user_id}).first()
        if not target or not target[0]:
            raise ValueError('Target account does not exist or is inactive. The person must sign in first.')
        before = conn.execute(text('SELECT role,is_active FROM tenant_memberships WHERE tenant_id=:t AND user_id=:u'),
                              {'t':tenant,'u':target_user_id}).mappings().first()
        before = dict(before) if before else None
        after = {'role':role,'is_active':active}
        if before == after:
            return False
        conn.execute(text('''INSERT INTO tenant_memberships(tenant_id,user_id,role,is_active)
            VALUES(:t,:u,:r,:active) ON CONFLICT(tenant_id,user_id)
            DO UPDATE SET role=EXCLUDED.role,is_active=EXCLUDED.is_active'''),
            {'t':tenant,'u':target_user_id,'r':role,'active':active})
        remaining = conn.execute(text('''SELECT count(*) FROM tenant_memberships m
            JOIN app_users u USING(user_id) WHERE m.tenant_id=:t AND m.role='admin'
            AND m.is_active AND u.is_active'''),{'t':tenant}).scalar_one()
        if not remaining:
            raise AccessDenied('Keep at least one active company administrator.')
        _membership_audit(conn,tenant,actor_id,target_user_id,before,after,'bootstrap' if bootstrap else 'membership_set')
    return True
