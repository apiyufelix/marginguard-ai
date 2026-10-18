"""Saved findings and transaction-protected case actions for the local portfolio app."""
from __future__ import annotations
import hashlib
import json
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text
from marginguard.workflow import CasePolicyError, required_text, transition_amount, validate_recovery
from marginguard.access import require_access

RULE_CODE = 'PRICE_UNDERBILLING'
RULE_VERSION = '1'

class CaseMigrationRequired(RuntimeError):
    pass

class CaseChanged(CasePolicyError):
    pass


def _ready(conn):
    if not conn.execute(text("SELECT 1 FROM schema_migrations WHERE version='003'")).scalar():
        raise CaseMigrationRequired('Apply migration 003 before using investigations.')


def _params(tenant):
    return {'tenant':tenant,'rule':RULE_CODE,'rule_version':RULE_VERSION}


def _event(conn, tenant, finding, event_type, actor, details, request_key=None,
           amount=None, reverses=None):
    event_id = str(uuid4())
    verified = conn.info.get('marginguard_actor')
    if verified is not None:
        actor = verified['display_name']
        conn.execute(text('''INSERT INTO case_events
            (tenant_id,event_id,finding_id,event_type,actor,actor_user_id,details,request_key,amount,reverses_event_id)
            VALUES(:tenant,:event,:finding,:type,:actor,:user_id,CAST(:details AS jsonb),:request,:amount,:reverses)'''),
            {'tenant':tenant,'event':event_id,'finding':finding,'type':event_type,'actor':actor,'user_id':verified['user_id'],
             'details':json.dumps(details,default=str),'request':request_key,'amount':amount,'reverses':reverses})
        return event_id
    conn.execute(text('''INSERT INTO case_events
        (tenant_id,event_id,finding_id,event_type,actor,details,request_key,amount,reverses_event_id)
        VALUES(:tenant,:event,:finding,:type,:actor,CAST(:details AS jsonb),:request,:amount,:reverses)'''),
        {'tenant':tenant,'event':event_id,'finding':finding,'type':event_type,'actor':actor,
         'details':json.dumps(details,default=str),'request':request_key,'amount':amount,'reverses':reverses})
    return event_id


def run_detection(engine, tenant):
    """Persist newly observed discrepancies. Repeated scans preserve review decisions."""
    created = 0
    with engine.begin() as conn:
        require_access(conn,tenant,'write')
        _ready(conn)
        conn.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:tenant,0))'),{'tenant':tenant})
        if not conn.execute(text('SELECT 1 FROM tenants WHERE tenant_id=:tenant'),{'tenant':tenant}).scalar():
            raise CasePolicyError('Configured organization does not exist.')
        rows = conn.execute(text("SELECT * FROM underbilling_candidates WHERE tenant_id=:tenant ORDER BY invoice_line_id"),{'tenant':tenant}).mappings().all()
        for row in rows:
            finding_id = str(uuid4())
            evidence = {k:v for k,v in dict(row).items() if k!='tenant_id'}
            evidence['basis'] = 'Posted invoice quantity times the positive difference between agreed and billed net unit prices; before tax.'
            inserted = conn.execute(text('''INSERT INTO findings
                (tenant_id,finding_id,invoice_line_id,rule_code,rule_version,potential_loss,evidence)
                VALUES(:tenant,:finding,:line,:rule,:rule_version,:loss,CAST(:evidence AS jsonb))
                ON CONFLICT(tenant_id,rule_code,rule_version,invoice_line_id) DO NOTHING
                RETURNING finding_id'''),{**_params(tenant),'finding':finding_id,'line':row['invoice_line_id'],
                'loss':row['potential_loss'],'evidence':json.dumps(evidence,default=str)}).scalar()
            if inserted:
                _event(conn,tenant,finding_id,'created','MarginGuard rule engine',
                       {'rule_code':RULE_CODE,'rule_version':RULE_VERSION,'potential_loss':str(row['potential_loss'])})
                created += 1
    return {'candidates':len(rows),'created':created,'already_saved':len(rows)-created}


def list_cases(conn, tenant):
    require_access(conn,tenant)
    _ready(conn)
    return [dict(x) for x in conn.execute(text('''SELECT f.*,
        COALESCE(r.net_recovered,0) AS net_recovered
        FROM findings f LEFT JOIN (
            SELECT tenant_id,finding_id,sum(CASE WHEN event_type='recovery' THEN amount
                WHEN event_type='recovery_reversal' THEN -amount ELSE 0 END) AS net_recovered
            FROM case_events WHERE tenant_id=:tenant GROUP BY tenant_id,finding_id
        ) r USING(tenant_id,finding_id)
        WHERE f.tenant_id=:tenant AND f.rule_code=:rule AND f.rule_version=:rule_version
        ORDER BY f.potential_loss DESC,f.created_at,f.finding_id'''),_params(tenant)).mappings()]


def summarize(cases):
    confirmed = sum((x['confirmed_amount'] or Decimal('0') for x in cases),Decimal('0'))
    recovered = sum((x['net_recovered'] for x in cases),Decimal('0'))
    return {'saved_findings':len(cases),'confirmed_amount':confirmed,'net_recovered':recovered,
            'confirmed_outstanding':confirmed-recovered}


def get_case(conn, tenant, finding):
    require_access(conn,tenant)
    _ready(conn)
    result = conn.execute(text('''SELECT * FROM findings WHERE tenant_id=:tenant AND finding_id=:finding
        AND rule_code=:rule AND rule_version=:rule_version'''),{**_params(tenant),'finding':finding}).mappings().first()
    if not result:
        raise CasePolicyError('Case was not found in this organization.')
    events = [dict(x) for x in conn.execute(text('''SELECT * FROM case_events
        WHERE tenant_id=:tenant AND finding_id=:finding ORDER BY event_sequence'''),{'tenant':tenant,'finding':finding}).mappings()]
    net = sum((x['amount'] if x['event_type']=='recovery' else -x['amount'] if x['event_type']=='recovery_reversal' else Decimal('0') for x in events),Decimal('0'))
    return {**dict(result),'events':events,'net_recovered':net}


def active_recoveries(case):
    reversed_ids = {x['reverses_event_id'] for x in case['events'] if x['event_type']=='recovery_reversal'}
    return [x for x in case['events'] if x['event_type']=='recovery' and x['event_id'] not in reversed_ids]


def _apply(engine, tenant, finding, actor, expected_version, request_key, action, payload, handler):
    actor = required_text(actor,'Activity author',128)
    request_key = required_text(request_key,'Action identifier',128)
    with engine.begin() as conn:
        verified = require_access(conn,tenant,'write')
        actor_key = str(verified['user_id']) if verified else actor
        fingerprint = hashlib.sha256(json.dumps({'finding':finding,'actor':actor_key,'action':action,'payload':payload},sort_keys=True,default=str).encode()).hexdigest()
        _ready(conn)
        row = conn.execute(text('''SELECT finding_id,version FROM findings
            WHERE tenant_id=:tenant AND finding_id=:finding AND rule_code=:rule AND rule_version=:rule_version
            FOR UPDATE'''),{**_params(tenant),'finding':finding}).mappings().first()
        if not row:
            raise CasePolicyError('Case was not found in this organization.')
        previous = conn.execute(text('SELECT event_id,details FROM case_events WHERE tenant_id=:tenant AND request_key=:request'),{'tenant':tenant,'request':request_key}).mappings().first()
        if previous:
            if previous['details'].get('request_fingerprint') != fingerprint:
                raise CasePolicyError('That action identifier was already used with different details.')
            return {'event_id':previous['event_id'],'replayed':True}
        if expected_version != row['version']:
            raise CaseChanged('This case changed since it was displayed. Refresh the case and review the latest values before submitting again.')
        case = get_case(conn,tenant,finding)
        event_type, details, amount, reverses = handler(conn,case)
        details['request_fingerprint'] = fingerprint
        event_id = _event(conn,tenant,finding,event_type,actor,details,request_key,amount,reverses)
        conn.execute(text('''UPDATE findings SET version=version+1,updated_at=now()
            WHERE tenant_id=:tenant AND finding_id=:finding'''),{'tenant':tenant,'finding':finding})
    return {'event_id':event_id,'replayed':False}


def assign_owner(engine,tenant,finding,owner,actor,expected_version,request_key):
    owner = str(owner).strip() if owner is not None else ''
    if owner:
        owner = required_text(owner,'Owner',128)
    owner = owner or None
    def handler(conn,case):
        if owner == case['assigned_to']:
            raise CasePolicyError('The owner is unchanged.')
        conn.execute(text('UPDATE findings SET assigned_to=:owner WHERE tenant_id=:tenant AND finding_id=:finding'),{'owner':owner,'tenant':tenant,'finding':finding})
        return 'assignment',{'previous_owner':case['assigned_to'],'owner':owner},None,None
    return _apply(engine,tenant,finding,actor,expected_version,request_key,'assignment',{'owner':owner},handler)


def add_note(engine,tenant,finding,note,actor,expected_version,request_key):
    note = required_text(note,'Note',4000)
    return _apply(engine,tenant,finding,actor,expected_version,request_key,'note',{'note':note},
                  lambda conn,case:('note',{'note':note},None,None))


def change_status(engine,tenant,finding,target,note,actor,expected_version,request_key,
                  confirmation=None,close_with_balance=False):
    note = required_text(note,'Reason')
    payload = {'target':target,'note':note,'confirmation':confirmation,'close_with_balance':close_with_balance}
    def handler(conn,case):
        confirmed = transition_amount(case['status'],target,case['potential_loss'],case['confirmed_amount'],
                                      case['net_recovered'],confirmation,close_with_balance)
        conn.execute(text('UPDATE findings SET status=:status,confirmed_amount=:confirmed WHERE tenant_id=:tenant AND finding_id=:finding'),
                     {'status':target,'confirmed':confirmed,'tenant':tenant,'finding':finding})
        return 'status_change',{'from':case['status'],'to':target,'reason':note,'confirmed_amount':confirmed,
             'unrecovered_balance_at_close':confirmed-case['net_recovered'] if target=='resolved' else None},None,None
    return _apply(engine,tenant,finding,actor,expected_version,request_key,'status_change',payload,handler)


def record_recovery(engine,tenant,finding,amount,reference,note,actor,expected_version,request_key):
    reference = required_text(reference,'Recovery reference',128)
    note = required_text(note,'Recovery note')
    payload = {'amount':str(amount),'reference':reference,'note':note}
    def handler(conn,case):
        value = validate_recovery(case['status'],case['confirmed_amount'],case['net_recovered'],amount)
        if any(x['details'].get('reference','').casefold()==reference.casefold() for x in active_recoveries(case)):
            raise CasePolicyError('This case already has an active recovery with that reference.')
        return 'recovery',{'reference':reference,'note':note},value,None
    return _apply(engine,tenant,finding,actor,expected_version,request_key,'recovery',payload,handler)


def reverse_recovery(engine,tenant,finding,event_id,note,actor,expected_version,request_key):
    note = required_text(note,'Reversal reason')
    def handler(conn,case):
        if case['status']!='confirmed':
            raise CasePolicyError('Reopen a resolved case to confirmed before reversing a recovery.')
        original = next((x for x in active_recoveries(case) if x['event_id']==event_id),None)
        if not original:
            raise CasePolicyError('Select an active recovery on this case; it may already have been reversed.')
        return 'recovery_reversal',{'reason':note,'original_reference':original['details'].get('reference')},original['amount'],event_id
    return _apply(engine,tenant,finding,actor,expected_version,request_key,'recovery_reversal',{'event_id':event_id,'note':note},handler)
