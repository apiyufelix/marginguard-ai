import copy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
import unittest

from marginguard.analytics import customer_options, dashboard_model, date_bounds, make_snapshot

STAMP = datetime(2026, 10, 18, tzinfo=timezone.utc)


def snapshot():
    orders = [{'order_id': 'O1', 'customer_id': 'C1', 'customer_name': 'Same name'},
              {'order_id': 'O2', 'customer_id': 'C2', 'customer_name': 'Same name'},
              {'order_id': 'O3', 'customer_id': 'C3', 'customer_name': 'Case-only customer'}]

    def source(line, order, day, product, amount):
        return {'invoice_line_id': line, 'invoice_id': 'I' + line, 'order_id': order,
                'invoice_date': day, 'product_id': product, 'sku': 'Same SKU label',
                'potential_loss': D(amount)}

    rows = [source('IL1', 'O1', date(2026, 1, 10), 'P1', '20.00'),
            source('IL2', 'O2', date(2026, 1, 15), 'P2', '40.00'),
            source('IL3', 'O1', date(2026, 3, 5), 'P1', '10.00')]

    def case(key, evidence, status, confirmed, recovered, created, owner=None):
        return {'finding_id': key, 'invoice_line_id': evidence['invoice_line_id'],
                'status': status, 'assigned_to': owner, 'potential_loss': evidence['potential_loss'],
                'confirmed_amount': D(confirmed) if confirmed is not None else None,
                'net_recovered': D(recovered), 'created_at': created,
                'evidence': {**evidence, 'invoice_date': str(evidence['invoice_date'])}}

    cases = [case('F1', rows[0], 'open', None, '0.00', datetime(2026, 10, 1, tzinfo=timezone.utc)),
             case('F2', rows[1], 'confirmed', '30.00', '10.00', datetime(2026, 9, 1, tzinfo=timezone.utc), 'Demo reviewer'),
             case('F3', rows[2], 'resolved', '10.00', '4.00', datetime(2026, 8, 1, tzinfo=timezone.utc)),
             case('F4', source('IL4', 'O3', date(2026, 2, 1), 'P3', '100.00'), 'dismissed', None, '0.00', STAMP)]
    return make_snapshot(rows, cases, orders, 'Fictional distributor', STAMP)


class DashboardAnalytics(unittest.TestCase):
    def test_exact_source_and_saved_metrics_stay_separate(self):
        model = dashboard_model(snapshot())
        self.assertEqual((model['potential_underbilling'], model['candidate_lines']), (D('70.00'), 3))
        self.assertEqual((model['confirmed_amount'], model['net_recovered'], model['confirmed_outstanding']),
                         (D('40.00'), D('14.00'), D('26.00')))
        self.assertEqual((model['saved_findings'], model['customer_count'], model['product_count']), (4, 2, 2))
        self.assertEqual(model['recovery_percent'], D('35.0'))
        self.assertIsInstance(model['potential_underbilling'], D)

    def test_customer_id_and_inclusive_invoice_dates_filter_both_sources(self):
        data = snapshot()
        model = dashboard_model(data, customer_id='C1', start=date(2026, 1, 10), end=date(2026, 1, 10))
        self.assertEqual((model['candidate_lines'], model['saved_findings'], model['potential_underbilling']), (1, 1, D('20.00')))
        self.assertEqual(model['confirmed_amount'], D('0'))
        # The saved case was created in August, but belongs to its March invoice cohort.
        march = dashboard_model(data, start=date(2026, 3, 5), end=date(2026, 3, 5))
        self.assertEqual((march['confirmed_amount'], march['net_recovered']), (D('10.00'), D('4.00')))
        self.assertEqual(dashboard_model(data, customer_id='C2')['potential_underbilling'], D('40.00'))

    def test_unknown_dates_remain_in_all_time_totals_and_leave_date_cohorts(self):
        data = snapshot()
        data['candidates'][0]['invoice_date'] = None
        data['cases'][0]['invoice_date'] = None
        all_time = dashboard_model(data)
        self.assertEqual(all_time['potential_underbilling'], D('70.00'))
        self.assertEqual(sum(row['potential_loss'] for row in all_time['monthly']), D('50.00'))
        filtered = dashboard_model(data, start=date(2026, 1, 1), end=date(2026, 12, 31))
        self.assertEqual((filtered['candidate_lines'], filtered['saved_findings']), (2, 3))
        self.assertEqual((filtered['undated_candidates'], filtered['undated_cases']), (1, 1))

    def test_monthly_series_fills_interior_gaps_without_floating_point_math(self):
        data = snapshot()
        data['candidates'][1]['invoice_date'] = date(2026, 3, 5)
        monthly = dashboard_model(data)['monthly']
        self.assertEqual([row['month'] for row in monthly], ['2026-01', '2026-02', '2026-03'])
        self.assertEqual([row['potential_loss'] for row in monthly], [D('20.00'), D('0.00'), D('50.00')])
        self.assertTrue(all(isinstance(row['potential_loss'], D) for row in monthly))

    def test_concentrations_keep_duplicate_names_and_sku_labels_distinct(self):
        model = dashboard_model(snapshot())
        self.assertEqual([row['id'] for row in model['customers']], ['C2', 'C1'])
        self.assertEqual([row['id'] for row in model['products']], ['P2', 'P1'])
        self.assertEqual(model['customers'][0]['share_percent'], D('57.1'))
        self.assertEqual(sum(row['potential_loss'] for row in model['customers']), D('70.00'))
        self.assertEqual(sum(row['potential_loss'] for row in model['products']), D('70.00'))

    def test_resolved_outstanding_and_dismissal_are_not_recoveries_or_active_work(self):
        model = dashboard_model(snapshot())
        statuses = {row['status']: row for row in model['status_breakdown']}
        self.assertEqual(statuses['resolved']['confirmed_outstanding'], D('6.00'))
        self.assertEqual(statuses['dismissed']['net_recovered'], D('0.00'))
        self.assertEqual(model['closed_outstanding'], D('6.00'))
        self.assertEqual({row['finding_id'] for row in model['priorities']}, {'F1', 'F2'})
        self.assertEqual(sum(row['cases'] for row in model['active_aging']), 2)

    def test_recovery_rate_is_undefined_without_confirmations(self):
        data = snapshot()
        data['cases'] = [data['cases'][0]]
        self.assertIsNone(dashboard_model(data)['recovery_percent'])
        data['cases'][0].update(status='confirmed', confirmed_amount=D('20.00'), net_recovered=D('0.00'))
        self.assertEqual(dashboard_model(data)['recovery_percent'], D('0.0'))

    def test_active_aging_uses_utc_case_creation_with_boundary_and_unknown_bands(self):
        data = snapshot()
        template = data['cases'][0]
        ages = [0, 7, 8, 30, 31, 60, 61, None, -1]
        data['cases'] = [{**template, 'finding_id': str(index),
                          'created_at': STAMP - timedelta(days=age) if age is not None else None}
                         for index, age in enumerate(ages)]
        model = dashboard_model(data)
        self.assertEqual([row['cases'] for row in model['active_aging']], [2, 2, 2, 1, 2])
        self.assertEqual(model['active_aged_30_days'], 4)
        self.assertEqual(model['active_unassigned'], 9)
        data['cases'] = [{**template, 'created_at': '2026-10-17T23:30:00-04:00'}]
        # Timestamp is later on the same UTC calendar date: calendar age is zero.
        self.assertEqual(dashboard_model(data)['priorities'][0]['age_days'], 0)

    def test_priorities_use_remaining_confirmed_amount_and_keep_closure_work(self):
        data = snapshot()
        model = dashboard_model(data)
        self.assertEqual([row['finding_id'] for row in model['priorities']], ['F2', 'F1'])
        self.assertEqual(model['priorities'][0]['review_amount'], D('20.00'))
        self.assertEqual(model['priorities'][0]['amount_basis'], 'Confirmed outstanding')
        data['cases'][1]['net_recovered'] = D('30.00')
        model = dashboard_model(data)
        self.assertEqual([row['finding_id'] for row in model['priorities']], ['F1', 'F2'])
        self.assertEqual(model['priorities'][1]['review_amount'], D('0.00'))

    def test_filter_options_include_saved_only_customers_and_unknown_metadata(self):
        data = snapshot()
        self.assertEqual({row['customer_id'] for row in customer_options(data)}, {'C1', 'C2', 'C3'})
        self.assertEqual(date_bounds(data), (date(2026, 1, 10), date(2026, 3, 5)))
        incomplete = make_snapshot([{'invoice_line_id': 'IL', 'potential_loss': D('1.00')}], [], [], 'Demo', STAMP)
        self.assertEqual(customer_options(incomplete), [])
        self.assertIsNone(date_bounds(incomplete))
        model = dashboard_model(incomplete)
        self.assertEqual((model['customer_count'], model['product_count']), (0, 0))
        self.assertEqual(model['customers'][0]['label'], 'Unknown customer')

    def test_empty_and_no_match_selections_have_stable_zero_metrics(self):
        empty = dashboard_model(make_snapshot([], [], [], 'Demo', STAMP))
        self.assertEqual((empty['candidate_lines'], empty['saved_findings']), (0, 0))
        self.assertEqual(empty['potential_underbilling'], D('0.00'))
        self.assertEqual(empty['priorities'], [])
        self.assertEqual(len(empty['status_breakdown']), 5)
        self.assertEqual(dashboard_model(snapshot(), customer_id='absent')['confirmed_amount'], D('0.00'))

    def test_invalid_boundaries_timestamps_and_financial_values_fail_explicitly(self):
        with self.assertRaises(ValueError):
            dashboard_model(snapshot(), start=date(2026, 2, 1), end=date(2026, 1, 1))
        with self.assertRaises(ValueError):
            dashboard_model(snapshot(), start='2026-01-01')
        with self.assertRaises(ValueError):
            dashboard_model(snapshot(), as_of=datetime(2026, 10, 18))
        for value in ('NaN', 'Infinity', '-1', None):
            data = snapshot(); data['candidates'][0]['potential_loss'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                dashboard_model(data)
        data = snapshot(); data['cases'][1]['net_recovered'] = D('31')
        with self.assertRaises(ValueError):
            dashboard_model(data)

    def test_models_and_snapshots_do_not_mutate_financial_source_objects(self):
        data = snapshot(); before = copy.deepcopy(data)
        dashboard_model(data, customer_id='C1'); customer_options(data); date_bounds(data)
        self.assertEqual(data, before)
        original = data['cases'][0]['evidence'].copy()
        make_snapshot(data['candidates'], data['cases'], [], 'Demo', STAMP)
        self.assertEqual(data['cases'][0]['evidence'], original)

    def test_priority_list_has_a_deterministic_top_ten(self):
        data = snapshot(); template = data['cases'][0]
        data['cases'] = [{**template, 'finding_id': f'F{index:02}', 'potential_loss': D(index)} for index in range(15)]
        priorities = dashboard_model(data)['priorities']
        self.assertEqual(len(priorities), 10)
        self.assertEqual([row['finding_id'] for row in priorities], [f'F{index:02}' for index in range(14, 4, -1)])
