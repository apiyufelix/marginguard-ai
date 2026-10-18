"""Read-only dashboard snapshots and exact, invoice-cohort analytics."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ZERO = Decimal('0.00')
STATUSES = ('open', 'investigating', 'confirmed', 'resolved', 'dismissed')
ACTIVE_STATUSES = ('open', 'investigating', 'confirmed')
AGE_BANDS = ('0–7 days', '8–30 days', '31–60 days', '61+ days', 'Unknown age')


def _amount(value, *, optional=False):
    if value is None and optional:
        return ZERO
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('A required dashboard amount is invalid.') from None
    if not number.is_finite() or number < 0:
        raise ValueError('Dashboard amounts must be finite and nonnegative.')
    return number


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _utc(value=None):
    value = value or datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Dashboard timestamps must be timezone-aware.')
    return value.astimezone(timezone.utc)


def _age(created_at, as_of):
    try:
        created = datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at
        days = (as_of.date() - _utc(created).date()).days if created is not None else None
        return days if days is not None and days >= 0 else None
    except (ValueError, TypeError):
        return None


def make_snapshot(candidates, cases, orders, organization, loaded_at=None):
    """Add filter dimensions without altering saved evidence or financial values."""
    lookup = {row['order_id']: row for row in orders}

    def dimensions(source):
        order = lookup.get(source.get('order_id'), {})
        return {
            'invoice_date': _date(source.get('invoice_date')),
            'customer_id': order.get('customer_id'),
            'customer_name': order.get('customer_name') or source.get('customer_name') or 'Unknown customer',
            'product_id': source.get('product_id'),
            'sku': source.get('sku') or 'Unknown product',
        }

    return {
        'organization': organization,
        'loaded_at_utc': _utc(loaded_at),
        'candidates': [{**row, **dimensions(row)} for row in candidates],
        'cases': [{**case, **dimensions(case.get('evidence') or {})} for case in cases],
    }


def read_dashboard(engine, tenant):
    """Read related totals from one tenant-scoped, read-only PostgreSQL snapshot."""
    from sqlalchemy import text
    from marginguard.cases import list_cases

    with engine.begin() as conn:
        conn.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        organization = conn.execute(text('SELECT name FROM tenants WHERE tenant_id=:tenant'), {'tenant': tenant}).scalar()
        if organization is None:
            raise ValueError('The configured organization does not exist.')
        cases = list_cases(conn, tenant)
        candidates = [dict(row) for row in conn.execute(text('''
            SELECT * FROM underbilling_candidates
            WHERE tenant_id=:tenant ORDER BY potential_loss DESC,invoice_line_id
        '''), {'tenant': tenant}).mappings()]
        orders = [dict(row) for row in conn.execute(text('''
            SELECT o.order_id,o.customer_id,c.name AS customer_name
            FROM orders o JOIN customers c
              ON c.tenant_id=o.tenant_id AND c.customer_id=o.customer_id
            WHERE o.tenant_id=:tenant
        '''), {'tenant': tenant}).mappings()]
    return make_snapshot(candidates, cases, orders, organization)


def customer_options(snapshot):
    customers = {row['customer_id']: row['customer_name']
                 for row in snapshot['candidates'] + snapshot['cases'] if row.get('customer_id') is not None}
    return [{'customer_id': key, 'label': f'{name} · {key}'}
            for key, name in sorted(customers.items(), key=lambda pair: (pair[1].casefold(), pair[0]))]


def date_bounds(snapshot):
    days = [_date(row.get('invoice_date')) for row in snapshot['candidates'] + snapshot['cases']]
    days = [day for day in days if day is not None]
    return (min(days), max(days)) if days else None


def _filter(rows, customer_id, start, end):
    selected = []
    for row in rows:
        if customer_id is not None and row.get('customer_id') != customer_id:
            continue
        day = _date(row.get('invoice_date'))
        if (start is not None or end is not None) and day is None:
            continue
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        selected.append(row)
    return selected


def _concentrations(rows, dimension, total):
    key_name, label_name = ('customer_id', 'customer_name') if dimension == 'customer' else ('product_id', 'sku')
    grouped = {}
    for row in rows:
        key = row.get(key_name)
        group = grouped.setdefault(key, {'id': key, 'label': row[label_name], 'invoice_lines': 0, 'potential_loss': ZERO})
        group['invoice_lines'] += 1
        group['potential_loss'] += _amount(row['potential_loss'])
    for group in grouped.values():
        group['share_percent'] = (group['potential_loss'] * 100 / total).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP) if total else ZERO
    return sorted(grouped.values(), key=lambda group: (-group['potential_loss'], str(group['id'])))


def _monthly(rows):
    grouped = {}
    for row in rows:
        day = _date(row.get('invoice_date'))
        if day is not None:
            month = day.year * 12 + day.month - 1
            grouped[month] = grouped.get(month, ZERO) + _amount(row['potential_loss'])
    if not grouped:
        return []
    return [{'month': f'{month // 12:04d}-{month % 12 + 1:02d}', 'potential_loss': grouped.get(month, ZERO)}
            for month in range(min(grouped), max(grouped) + 1)]


def dashboard_model(snapshot, *, customer_id=None, start=None, end=None, as_of=None):
    """Invoice-date filters select cohorts; recoveries retain their current net value."""
    for boundary in (start, end):
        if boundary is not None and (not isinstance(boundary, date) or isinstance(boundary, datetime)):
            raise ValueError('Invoice-date boundaries must be dates.')
    if start is not None and end is not None and start > end:
        raise ValueError('The start date must not be after the end date.')
    now = _utc(as_of or snapshot['loaded_at_utc'])
    candidates = _filter(snapshot['candidates'], customer_id, start, end)
    cases = _filter(snapshot['cases'], customer_id, start, end)
    potential = sum((_amount(row['potential_loss']) for row in candidates), ZERO)
    confirmed = sum((_amount(case.get('confirmed_amount'), optional=True) for case in cases), ZERO)
    recovered = sum((_amount(case['net_recovered']) for case in cases), ZERO)
    if recovered > confirmed:
        raise ValueError('Recorded recoveries exceed the confirmed total; review the case ledger.')
    status_rows = {status: {'status': status, 'cases': 0, 'potential_loss': ZERO,
                   'confirmed_amount': ZERO, 'net_recovered': ZERO, 'confirmed_outstanding': ZERO} for status in STATUSES}
    aging = {band: 0 for band in AGE_BANDS}
    priorities = []
    active_unassigned = aged_30 = 0
    closed_outstanding = ZERO
    for case in cases:
        status = case['status']
        if status not in status_rows:
            raise ValueError('Unknown investigation status.')
        loss = _amount(case['potential_loss'])
        confirmation = _amount(case.get('confirmed_amount'), optional=True)
        recovery = _amount(case['net_recovered'])
        if recovery > confirmation:
            raise ValueError('A case recovery exceeds its confirmation; review the case ledger.')
        outstanding = confirmation - recovery
        group = status_rows[status]
        group['cases'] += 1
        for field, value in (('potential_loss', loss), ('confirmed_amount', confirmation),
                             ('net_recovered', recovery), ('confirmed_outstanding', outstanding)):
            group[field] += value
        if status == 'resolved':
            closed_outstanding += outstanding
        if status not in ACTIVE_STATUSES:
            continue
        age = _age(case.get('created_at'), now)
        band = 'Unknown age' if age is None else '0–7 days' if age <= 7 else '8–30 days' if age <= 30 else '31–60 days' if age <= 60 else '61+ days'
        aging[band] += 1
        active_unassigned += int(not case.get('assigned_to'))
        aged_30 += int(age is not None and age >= 30)
        priorities.append({
            'finding_id': case['finding_id'], 'invoice_line_id': case['invoice_line_id'],
            'customer_name': case['customer_name'], 'status': status,
            'owner': case.get('assigned_to') or 'Unassigned', 'age_days': age,
            'amount_basis': 'Confirmed outstanding' if case.get('confirmed_amount') is not None else 'Potential underbilling',
            'review_amount': outstanding if case.get('confirmed_amount') is not None else loss,
        })
    priorities.sort(key=lambda row: (-row['review_amount'], -row['age_days'] if row['age_days'] is not None else 1, row['finding_id']))
    before_dates_candidates = _filter(snapshot['candidates'], customer_id, None, None)
    before_dates_cases = _filter(snapshot['cases'], customer_id, None, None)
    return {
        'potential_underbilling': potential, 'candidate_lines': len(candidates),
        'customer_count': len({row['customer_id'] for row in candidates if row.get('customer_id') is not None}),
        'product_count': len({row['product_id'] for row in candidates if row.get('product_id') is not None}),
        'saved_findings': len(cases), 'confirmed_amount': confirmed, 'net_recovered': recovered,
        'confirmed_outstanding': confirmed - recovered,
        'recovery_percent': (recovered * 100 / confirmed).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP) if confirmed else None,
        'active_unassigned': active_unassigned, 'active_aged_30_days': aged_30,
        'closed_outstanding': closed_outstanding,
        'monthly': _monthly(candidates),
        'customers': _concentrations(candidates, 'customer', potential),
        'products': _concentrations(candidates, 'product', potential),
        'status_breakdown': list(status_rows.values()),
        'active_aging': [{'age_band': band, 'cases': count} for band, count in aging.items()],
        'priorities': priorities[:10], 'candidates': candidates,
        'undated_candidates': sum(_date(row.get('invoice_date')) is None for row in before_dates_candidates),
        'undated_cases': sum(_date(row.get('invoice_date')) is None for row in before_dates_cases),
    }
