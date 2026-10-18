import copy
import csv
from datetime import datetime,timezone
from decimal import Decimal as D
import io
import json
import unittest
from marginguard.reporting import case_payload,explain_case,filename,html_report,json_report,queue_csv

STAMP=datetime(2026,10,17,23,0,tzinfo=timezone.utc)

def example_case():
    return {'tenant_id':'demo-distributor','finding_id':'EXAMPLE-CASE-001','invoice_line_id':'IMP-IL001',
        'rule_code':'PRICE_UNDERBILLING','rule_version':'1','version':4,'status':'confirmed',
        'assigned_to':'Demo reviewer','created_at':STAMP,'updated_at':STAMP,
        'potential_loss':D('20.00'),'confirmed_amount':D('20.00'),'net_recovered':D('10.00'),
        'evidence':{'invoice_id':'IMP-I001','order_id':'IMP-O001','order_line_id':'IMP-OL001',
            'invoice_line_id':'IMP-IL001','customer_name':'Fictional Demo Customer','sku':'MG-DEMO',
            'quantity':10,'agreed_net_unit_price':'20.0000','invoiced_net_unit_price':'18.0000','potential_loss':'20.00',
            'order_source_batch':'DEMO-ORDER-BATCH','order_source_row':2,
            'invoice_source_batch':'DEMO-INVOICE-BATCH','invoice_source_row':2},
        'events':[
            {'event_id':'E1','event_type':'created','actor':'MarginGuard rule engine','created_at':STAMP,'amount':None,'details':{'potential_loss':'20.00'}},
            {'event_id':'E2','event_type':'status_change','actor':'Demo reviewer','created_at':STAMP,'amount':None,'details':{'from':'investigating','to':'confirmed','reason':'Synthetic evidence review','confirmed_amount':'20.00'}},
            {'event_id':'E3','event_type':'recovery','actor':'Demo reviewer','created_at':STAMP,'amount':D('10.00'),
             'request_key':'private-action-token','details':{'reference':'DEMO-REC-001','note':'Synthetic portfolio test','request_fingerprint':'private-hash'}},
        ]}

class CaseReporting(unittest.TestCase):
    def test_summary_preserves_exact_recorded_amounts_and_reconciliation(self):
        case=example_case();analysis=explain_case(case)
        self.assertTrue(analysis['calculation_reconciles'])
        self.assertEqual(analysis['quality_issues'],[])
        self.assertIn('$20.00',analysis['summary'])
        self.assertIn('$10.00',analysis['review_summary'])
        self.assertTrue(any('$10.00' in x for x in analysis['recommended_checks']))

    def test_open_case_uses_hypotheses_not_asserted_root_causes(self):
        case=example_case();case.update(status='open',confirmed_amount=None,net_recovered=D('0'),events=[])
        analysis=explain_case(case)
        self.assertEqual(len(analysis['possible_explanations']),3)
        self.assertIn('No amount has been confirmed',analysis['review_summary'])
        self.assertFalse(any('already recovered' in x for x in analysis['recommended_checks']))
        self.assertIsNone(case_payload(case,STAMP)['amounts']['confirmed_outstanding'])

    def test_closed_balance_is_never_reported_as_recovered(self):
        case=example_case();case['status']='resolved'
        analysis=explain_case(case)
        self.assertIn('$10.00 still outstanding',analysis['review_summary'])
        self.assertTrue(any('reopen' in x for x in analysis['recommended_checks']))
        case.update(net_recovered=D('20'))
        case['events'].append({'event_id':'E4','event_type':'recovery','amount':D('10'),'details':{},'created_at':STAMP,'actor':'Demo'})
        self.assertIn('$0.00',explain_case(case)['review_summary'])

    def test_missing_lineage_is_explicit_and_missing_values_are_not_invented(self):
        case=example_case();case['evidence']={}
        analysis=explain_case(case)
        self.assertIsNone(analysis['calculation_reconciles'])
        self.assertIn('unavailable',analysis['lineage_summary'])
        self.assertTrue(analysis['quality_issues'])
        case.update(potential_loss=None,net_recovered=None)
        self.assertIn('Not recorded',explain_case(case)['summary'])

    def test_pricing_mismatch_keeps_saved_amount_and_flags_issue(self):
        case=example_case();case['evidence']['invoiced_net_unit_price']='17'
        analysis=explain_case(case)
        self.assertFalse(analysis['calculation_reconciles'])
        self.assertTrue(any('$30.00' in x and '$20.00' in x for x in analysis['quality_issues']))
        self.assertEqual(case_payload(case,STAMP)['amounts']['potential_underbilling'],D('20.00'))

    def test_ledger_mismatch_is_reported(self):
        case=example_case();case['net_recovered']=D('12')
        self.assertTrue(any('activity does not reconcile' in x for x in explain_case(case)['quality_issues']))

    def test_reversal_changes_net_effect_without_erasing_original(self):
        case=example_case();case['events'].append({'event_id':'E4','event_type':'recovery_reversal','amount':D('10'),
            'reverses_event_id':'E3','details':{'reason':'Synthetic correction'},'created_at':STAMP,'actor':'Demo'})
        case['net_recovered']=D('0')
        payload=case_payload(case,STAMP)
        self.assertEqual(payload['amounts']['confirmed_outstanding'],D('20'))
        self.assertEqual(payload['case_activity'][-1]['signed_recovery_amount'],D('-10'))
        self.assertEqual(len(payload['case_activity']),4)
        self.assertEqual(payload['analysis']['quality_issues'],[])

    def test_json_preserves_decimals_and_excludes_private_request_metadata(self):
        data=json_report(example_case(),STAMP)
        parsed=json.loads(data)
        self.assertEqual(parsed['amounts']['confirmed_amount'],'20.00')
        self.assertEqual(parsed['generated_at_utc'],'2026-10-17T23:00:00+00:00')
        self.assertNotIn(b'private-hash',data)
        self.assertNotIn(b'private-action-token',data)
        self.assertEqual(parsed['analysis']['method'],'rule_based_v1')

    def test_html_escapes_untrusted_content_and_is_self_contained(self):
        case=example_case();case['assigned_to']='<script>alert(1)</script>'
        case['events'][-1]['details']['note']='<img src=x onerror=alert(1)>'
        page=html_report(case,STAMP).decode()
        self.assertNotIn('<script>',page)
        self.assertNotIn('<img ',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertIn('&lt;img',page)
        self.assertIn('Confirmed outstanding',page)
        self.assertNotIn('private-hash',page)
        self.assertNotIn('src="https://',page)

    def test_csv_contains_only_requested_rows_and_exact_balances(self):
        data=queue_csv([example_case()],STAMP)
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['invoice_line_id'],'IMP-IL001')
        self.assertEqual(rows[0]['confirmed_amount'],'20.00')
        self.assertEqual(rows[0]['confirmed_outstanding'],'10.00')
        self.assertEqual(rows[0]['currency'],'USD')
        self.assertEqual(len(list(csv.DictReader(io.StringIO(queue_csv([],STAMP).decode('utf-8-sig'))))),0)

    def test_csv_neutralizes_formula_text_and_keeps_numeric_amounts(self):
        case=example_case();case['assigned_to']='=1+1';case['evidence']['customer_name']='  @SUM(1,2)'
        row=list(csv.DictReader(io.StringIO(queue_csv([case],STAMP).decode('utf-8-sig'))))[0]
        self.assertTrue(row['owner'].startswith("'="))
        self.assertTrue(row['customer_name'].startswith("'"))
        self.assertEqual(row['potential_underbilling'],'20.00')

    def test_export_does_not_mutate_case_or_turn_none_into_zero(self):
        case=example_case();before=copy.deepcopy(case)
        html_report(case,STAMP);json_report(case,STAMP);queue_csv([case],STAMP)
        self.assertEqual(case,before)
        case.update(status='open',confirmed_amount=None,net_recovered=D('0'),events=[])
        row=list(csv.DictReader(io.StringIO(queue_csv([case],STAMP).decode('utf-8-sig'))))[0]
        self.assertEqual(row['confirmed_amount'],'')
        self.assertEqual(row['confirmed_outstanding'],'')
        self.assertEqual(row['net_recorded_recoveries'],'0')

    def test_filenames_and_report_timestamps(self):
        case=example_case();case['invoice_line_id']='../../bad:<name>/é'
        self.assertNotIn('/',filename(case,'html'))
        self.assertNotIn('..',filename(case,'json'))
        with self.assertRaises(ValueError):filename(case,'exe')
        with self.assertRaises(ValueError):case_payload(case,datetime(2026,10,17))

    def test_invalid_evidence_and_recovery_amounts_surface_issues(self):
        for field,value in [('quantity','1.5'),('quantity','-1'),('agreed_net_unit_price','NaN'),('invoiced_net_unit_price','Infinity')]:
            case=example_case();case['evidence'][field]=value
            with self.subTest(field=field):self.assertTrue(explain_case(case)['quality_issues'])
        case=example_case();case['net_recovered']=D('21')
        self.assertTrue(any('above' in x for x in explain_case(case)['quality_issues']))
