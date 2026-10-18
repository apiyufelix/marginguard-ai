"""Evidence-based explanations and read-only exports. No AI API or database writes."""
from __future__ import annotations
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import html
import io
import json
import re

from marginguard.rules import underbilling


def _decimal(value):
    if value is None or value == '':
        return None
    try:
        result=Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _usd(value,missing='Not recorded',places=2):
    number=_decimal(value)
    return f'${number:,.{places}f}' if number is not None else missing


def _when(value):
    return value.isoformat() if isinstance(value,(datetime,date)) else str(value) if value is not None else ''


def _generated(value=None):
    value=value or datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Report timestamp must be timezone-aware.')
    return value.astimezone(timezone.utc).isoformat()


def _json_default(value):
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,(date,datetime)):return value.isoformat()
    raise TypeError(f'Unsupported export type: {type(value).__name__}')


def filename(case,suffix):
    if suffix not in ('html','json'):
        raise ValueError('Unsupported case report format.')
    identifier=case.get('invoice_line_id') or case.get('finding_id') or 'case'
    safe=re.sub(r'[^A-Za-z0-9_-]+','_',str(identifier)).strip('_')[:80] or 'case'
    return f'MarginGuard_case_{safe}.{suffix}'


def explain_case(case):
    """Keep recorded amounts authoritative; surface reconciliation issues explicitly."""
    evidence=case.get('evidence') or {}
    status=case.get('status','unknown')
    potential=_decimal(case.get('potential_loss'))
    confirmed=_decimal(case.get('confirmed_amount'))
    recovered=_decimal(case.get('net_recovered'))
    remaining=confirmed-recovered if confirmed is not None and recovered is not None else None
    agreed=_decimal(evidence.get('agreed_net_unit_price'))
    billed=_decimal(evidence.get('invoiced_net_unit_price'))
    quantity=_decimal(evidence.get('quantity'))
    issues=[]
    computed=None
    if agreed is not None and billed is not None and quantity is not None:
        try:
            if quantity!=quantity.to_integral_value():raise ValueError()
            computed=underbilling(quantity,agreed,billed)
        except (ValueError,InvalidOperation):
            issues.append('The captured quantity or prices cannot be used to reconcile the rule calculation.')
    else:
        issues.append('Captured quantity or pricing evidence is incomplete; the saved amount cannot be independently reconciled here.')
    if computed is not None and potential is not None and computed!=potential:
        issues.append(f'The captured prices calculate to {_usd(computed)}, while saved potential underbilling is {_usd(potential)}. Review the source discrepancy before confirming a new amount.')
    if potential is None or potential<0:
        issues.append('A valid nonnegative saved potential amount is unavailable.')
    if status in ('confirmed','resolved') and confirmed is None:
        issues.append('This status requires a recorded confirmation amount; it is missing or invalid.')
    if confirmed is not None and (confirmed<=0 or (potential is not None and confirmed>potential)):
        issues.append('The recorded confirmation amount is outside the valid range for this finding.')
    if recovered is None or recovered<0 or (confirmed is not None and recovered>confirmed):
        issues.append('The recorded recovery balance is missing, negative or above the confirmed amount.')
    if confirmed is None and recovered is not None and recovered!=0:
        issues.append('Recoveries are recorded without a valid confirmation amount.')
    if 'events' in case:
        ledger=Decimal('0');ledger_valid=True
        for event in case['events']:
            if event.get('event_type') in ('recovery','recovery_reversal'):
                amount=_decimal(event.get('amount'))
                if amount is None or amount<=0:
                    ledger_valid=False
                    break
                ledger+=amount if event['event_type']=='recovery' else -amount
        if not ledger_valid or (recovered is not None and ledger!=recovered):
            issues.append('The recovery activity does not reconcile to the displayed net recorded recovery balance.')
    line=str(case.get('invoice_line_id','Unavailable'))
    snapshot=(f"Saved evidence for invoice line {line} shows {quantity:g} units at {_usd(billed,places=4)} per unit, "
              f"compared with an agreed net price of {_usd(agreed,places=4)}. Saved potential underbilling is {_usd(potential)}."
              if quantity is not None and agreed is not None and billed is not None
              else f'Invoice line {line} has saved potential underbilling of {_usd(potential)}; complete the pricing evidence before relying on a recalculation.')
    if status in ('open','investigating'):
        decision=f'The case is {status}. No amount has been confirmed through the review workflow.'
    elif status=='dismissed':
        decision='The case is dismissed. The original price discrepancy remains in the evidence; dismissal is a review decision rather than a cash recovery.'
    elif status=='resolved' and remaining is not None and remaining>0:
        decision=f'The case is resolved with {_usd(remaining)} still outstanding from {_usd(confirmed)} confirmed. Recorded recoveries are {_usd(recovered)}. Closure does not count the remaining balance as recovered.'
    else:
        decision=f"The case is {status}, with {_usd(confirmed)} confirmed and {_usd(recovered)} in net recorded recoveries. Confirmed outstanding is {_usd(remaining)}."
    actions=[]
    if issues:
        actions.append('Reconcile the reported data-quality issues against the source records before confirming or recording further amounts.')
    if status in ('open','investigating','confirmed') and not case.get('assigned_to'):
        actions.append('Assign a reviewer who can access the original order, invoice and approved pricing records.')
    if status in ('open','investigating'):
        actions.extend([
            'Compare the agreed net price, effective date and approved customer discounts with the posted invoice.',
            'Check for authorized post-order price adjustments, credits or rebills before confirming the discrepancy.',
            'Document the evidence and confirm only the supported amount, or dismiss with a reason.',
        ])
    elif status=='confirmed':
        if remaining is not None and remaining>0:
            actions.extend([f'Reconcile the remaining {_usd(remaining)} with accounts receivable and the supporting financial records.',
                            'Record each supported recovery with a distinct active reference; keep unresolved balances visible.'])
        else:
            actions.append('Check the recovery references and supporting financial records, then resolve the case with a reason if review is complete.')
    elif status=='resolved':
        if remaining is not None and remaining>0:
            actions.append('Review the documented closure reason and remaining balance; reopen to confirmed if further recovery or a correction is supported.')
        else:
            actions.append('Retain the supporting recovery records. Reopen to confirmed before correcting a recorded receipt.')
    elif status=='dismissed':
        actions.append('Retain the dismissal reason and supporting pricing evidence; reopen to investigating if new information changes the review.')
    else:
        actions.append('Review the case status and complete the required investigation records.')
    has_lineage=all(evidence.get(k) is not None for k in ('order_source_batch','order_source_row','invoice_source_batch','invoice_source_row'))
    lineage=('Source batch and row pointers are recorded for both order and invoice evidence.' if has_lineage
             else 'Complete upload lineage is unavailable for this snapshot. Use its order and invoice identifiers to locate the original records; initial demo seeds predate upload lineage.')
    hypotheses=[
        'A price override may differ from the agreed net unit price.',
        'A pricing effective date or master-data change may not have reached invoicing.',
        'An approved adjustment may be absent from the captured order extract.',
    ] if status in ('open','investigating') else []
    return {'method':'rule_based_v1','summary':snapshot,'review_summary':decision,
            'possible_explanations':hypotheses,'recommended_checks':actions,
            'quality_issues':issues,'lineage_summary':lineage,
            'calculation_reconciles':computed==potential if computed is not None and potential is not None else None}


def case_payload(case,generated_at=None):
    events=[]
    for event in case.get('events',[]):
        amount=_decimal(event.get('amount'))
        signed=amount if event.get('event_type')=='recovery' else -amount if event.get('event_type')=='recovery_reversal' and amount is not None else None
        events.append({'event_id':event.get('event_id'),'event_type':event.get('event_type'),
                       'actor':event.get('actor'),
                       'actor_user_id':str(event['actor_user_id']) if event.get('actor_user_id') else None,
                       'recorded_at':event.get('created_at'),
                       'amount':amount,'signed_recovery_amount':signed,
                       'reverses_event_id':event.get('reverses_event_id'),
                       'details':{k:v for k,v in (event.get('details') or {}).items() if k not in ('request_fingerprint','request_key')}})
    confirmed=_decimal(case.get('confirmed_amount'));recovered=_decimal(case.get('net_recovered'))
    return {'report_schema_version':'1','generated_at_utc':_generated(generated_at),'currency':'USD',
        'organization':case.get('organization_name') or case.get('tenant_id') or 'Unavailable',
        'finding':{key:case.get(key) for key in ('finding_id','invoice_line_id','rule_code','rule_version','version','status','assigned_to','created_at','updated_at')},
        'amounts':{'potential_underbilling':_decimal(case.get('potential_loss')),'confirmed_amount':confirmed,
                   'net_recorded_recoveries':recovered,'confirmed_outstanding':confirmed-recovered if confirmed is not None and recovered is not None else None},
        'analysis':explain_case(case),'captured_evidence':case.get('evidence') or {},'case_activity':events}


def json_report(case,generated_at=None):
    return (json.dumps(case_payload(case,generated_at),default=_json_default,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def html_report(case,generated_at=None):
    report=case_payload(case,generated_at)
    esc=lambda value:html.escape(str(value) if value is not None else 'Not recorded',quote=True)
    analysis=report['analysis'];finding=report['finding'];amounts=report['amounts']
    def bullets(values):return '<ul>'+''.join('<li>'+esc(x)+'</li>' for x in values)+'</ul>'
    metrics=''.join('<div class="metric"><span>'+esc(label)+'</span><strong>'+esc(_usd(value))+'</strong></div>' for label,value in (
        ('Potential underbilling',amounts['potential_underbilling']),('Confirmed amount',amounts['confirmed_amount']),
        ('Net recorded recoveries',amounts['net_recorded_recoveries']),('Confirmed outstanding',amounts['confirmed_outstanding'])))
    evidence_rows=''.join('<tr><th>'+esc(key.replace('_',' '))+'</th><td>'+esc(value)+'</td></tr>' for key,value in report['captured_evidence'].items())
    activity_rows=''.join('<tr><td>'+esc(_when(event['recorded_at']))+'</td><td>'+esc(event['event_type'])+'</td><td>'+esc(event['actor'])+'</td><td>'+esc(_usd(event['signed_recovery_amount'] if event['signed_recovery_amount'] is not None else event['amount'],missing=''))+'</td><td>'+esc(json.dumps(event['details'],default=_json_default,ensure_ascii=False))+'</td></tr>' for event in report['case_activity'])
    issues=('<section class="issues"><h2>Data-quality issues</h2>'+bullets(analysis['quality_issues'])+'</section>') if analysis['quality_issues'] else ''
    hypotheses=('<h2>Possible explanations to verify</h2><p>These are hypotheses; the saved evidence does not establish the cause.</p>'+bullets(analysis['possible_explanations'])) if analysis['possible_explanations'] else ''
    document='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MarginGuard case report</title><style>
body{margin:0;background:#f1f5f9;color:#172b4d;font:15px/1.55 Arial,sans-serif}main{max-width:1050px;margin:32px auto;background:white;padding:38px;border-top:6px solid #0f766e}h1{font-size:29px;margin:4px 0 12px}h2{font-size:19px;margin:24px 0 8px}p{margin:8px 0;white-space:pre-wrap;overflow-wrap:anywhere}.brand{font-weight:bold;color:#0f766e}.meta{color:#52647b;font-size:13px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}.metric{border:1px solid #d8e2ed;border-radius:6px;padding:14px}.metric span{display:block;font-size:12px;color:#52647b}.metric strong{display:block;font-size:20px;margin-top:6px;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px}td,th{border:1px solid #d8e2ed;text-align:left;vertical-align:top;padding:8px;overflow-wrap:anywhere;white-space:pre-wrap}th{background:#f6f8fb}.evidence th{width:30%}li{margin-bottom:6px;overflow-wrap:anywhere}.issues{background:#fff7ed;border:1px solid #fdba74;padding:12px}footer{border-top:1px solid #d8e2ed;margin-top:28px;padding-top:12px;color:#52647b;font-size:12px}@media(max-width:750px){main{margin:0;padding:18px}.metrics{grid-template-columns:repeat(2,1fr)}}@media print{body{background:white}main{margin:0;padding:12mm;border:0;max-width:none}h2{break-after:avoid}.metric,tr{break-inside:avoid}}
</style></head><body><main>'''
    document+='<div class="brand">MARGINGUARD AI</div><h1>Investigation case report</h1>'
    document+='<p class="meta">Organization: '+esc(report['organization'])+' | Generated (UTC): '+esc(report['generated_at_utc'])+'</p>'
    document+='<p><strong>Invoice line:</strong> '+esc(finding['invoice_line_id'])+' | <strong>Status:</strong> '+esc(finding['status'])+' | <strong>Owner:</strong> '+esc(finding['assigned_to'] or 'Unassigned')+'</p>'
    document+='<p class="meta">Finding: '+esc(finding['finding_id'])+' | Rule: '+esc(finding['rule_code'])+' / '+esc(finding['rule_version'])+' | Case version: '+esc(finding['version'])+'</p><div class="metrics">'+metrics+'</div>'
    document+=issues+'<h2>Case summary</h2><p>'+esc(analysis['summary'])+'</p><p>'+esc(analysis['review_summary'])+'</p>'
    document+='<h2>Recommended checks</h2>'+bullets(analysis['recommended_checks'])+hypotheses
    document+='<h2>Source lineage</h2><p>'+esc(analysis['lineage_summary'])+'</p><h2>Captured evidence</h2><table class="evidence">'+evidence_rows+'</table>'
    document+='<h2>Case activity</h2><table><thead><tr><th>Recorded time</th><th>Action</th><th>Author</th><th>Recovery effect (USD)</th><th>Details</th></tr></thead><tbody>'+activity_rows+'</tbody></table>'
    document+='<footer>Rule-based report from captured evidence and recorded case activity. Authenticated activity is linked to account IDs in the JSON export; legacy author labels and assigned owners may be user-entered. Recovery entries require supporting financial records; the report does not verify bank settlement. Generated reports are snapshots.</footer></main></body></html>'
    return document.encode('utf-8')


def _csv_cell(value):
    if value is None:return ''
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,(date,datetime)):return value.isoformat()
    result=str(value)
    if result.lstrip().startswith(('=','+','-','@')) or result.startswith(('\t','\r','\n')):
        return "'"+result
    return result


def queue_csv(cases,generated_at=None):
    exported=_generated(generated_at)
    columns=['finding_id','invoice_line_id','invoice_id','customer_name','sku','status','owner','currency',
             'potential_underbilling','confirmed_amount','net_recorded_recoveries','confirmed_outstanding',
             'rule_code','rule_version','case_version','created_at','updated_at','exported_at_utc']
    output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(columns)
    for case in cases:
        evidence=case.get('evidence') or {}
        confirmed=_decimal(case.get('confirmed_amount'));recovered=_decimal(case.get('net_recovered'))
        values=[case.get('finding_id'),case.get('invoice_line_id'),evidence.get('invoice_id'),evidence.get('customer_name'),
                evidence.get('sku'),case.get('status'),case.get('assigned_to'),'USD',_decimal(case.get('potential_loss')),
                confirmed,recovered,confirmed-recovered if confirmed is not None and recovered is not None else None,
                case.get('rule_code'),case.get('rule_version'),case.get('version'),case.get('created_at'),case.get('updated_at'),exported]
        writer.writerow([_csv_cell(x) for x in values])
    return output.getvalue().encode('utf-8-sig')
