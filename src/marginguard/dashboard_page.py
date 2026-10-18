"""Executive dashboard for source comparisons and saved investigation progress."""
import pandas as pd
import streamlit as st

from marginguard.analytics import customer_options, dashboard_model, date_bounds, read_dashboard
from marginguard.cases import CaseMigrationRequired


def _usd(value):
    return f'${value:,.2f}'


def _concentration(rows, heading, label):
    st.subheader(heading)
    if not rows:
        st.caption('No candidates in this selection.')
        return
    top = rows[:10]
    chart = pd.DataFrame([{
        label: f"{row['id'] or 'Unknown ID'} · {row['label']}",
        'Potential underbilling (USD)': float(row['potential_loss']),
    } for row in top])
    st.bar_chart(chart, x=label, y='Potential underbilling (USD)', horizontal=True, color='#0f766e', sort=False, height=340)
    st.dataframe(pd.DataFrame([{
        label: row['label'], 'ID': row['id'] or 'Not captured', 'Invoice lines': row['invoice_lines'],
        'Potential underbilling': _usd(row['potential_loss']), 'Share of selection': f"{row['share_percent']:.1f}%",
    } for row in top]), hide_index=True, width='stretch')
    st.caption('Top 10 by potential amount. IDs appear first so shortened labels remain distinguishable; full names and IDs are listed in the table. Shares use all candidates in the current selection.')


def render_dashboard(engine, tenant):
    st.subheader('Margin protection overview')
    st.button('Refresh dashboard')
    try:
        snapshot = read_dashboard(engine, tenant)
    except CaseMigrationRequired:
        st.error('Apply migration 003 with python scripts/migrate_db.py before opening this dashboard.')
        return
    st.text(f"{snapshot['organization']} · Refreshed {snapshot['loaded_at_utc']:%Y-%m-%d %H:%M:%S} UTC")
    options = customer_options(snapshot)
    labels = {row['customer_id']: row['label'] for row in options}
    with st.expander('Dashboard filters', expanded=True):
        left, right = st.columns(2)
        customer = left.selectbox('Dashboard customer', [None, *labels],
                                  format_func=lambda value: 'All customers' if value is None else labels[value],
                                  key='dashboard_customer')
        filter_dates = right.checkbox('Filter by invoice date', key='dashboard_filter_dates')
        bounds = date_bounds(snapshot)
        start = end = None
        if bounds:
            selected = st.date_input('Dashboard invoice date range', value=bounds, format='YYYY-MM-DD',
                                     disabled=not filter_dates, key='dashboard_invoice_dates')
            if filter_dates:
                if not isinstance(selected, (tuple, list)) or len(selected) != 2:
                    st.info('Choose both a start and end invoice date.')
                    return
                start, end = selected
        elif filter_dates:
            st.info('Invoice dates are unavailable. Clear the date filter to review all records.')
            return
        st.caption('Filters select an invoice cohort. Saved confirmation and net recovery amounts are current balances for those cases, regardless of when the review or recovery happened.')
    model = dashboard_model(snapshot, customer_id=customer, start=start, end=end)
    if model['undated_candidates'] or model['undated_cases']:
        effect = 'excluded by the date filter' if filter_dates else 'included in totals and omitted from the monthly chart'
        st.caption(f"Missing invoice dates: {model['undated_candidates']} candidates and {model['undated_cases']} saved cases; {effect}.")

    st.subheader('Source price comparisons')
    a, b, c, d = st.columns(4)
    a.metric('Potential underbilling', _usd(model['potential_underbilling']))
    b.metric('Invoice lines to investigate', model['candidate_lines'])
    c.metric('Customers with candidates', model['customer_count'])
    d.metric('Products with candidates', model['product_count'])
    st.caption('Current posted-invoice price comparisons. These include candidates whose saved cases may already be dismissed or resolved; review actions do not rewrite source prices.')

    st.subheader('Investigation progress')
    a, b, c, d = st.columns(4)
    a.metric('Saved findings', model['saved_findings'])
    b.metric('Confirmed amount', _usd(model['confirmed_amount']))
    c.metric('Net recorded recoveries', _usd(model['net_recovered']))
    d.metric('Confirmed outstanding', _usd(model['confirmed_outstanding']))
    st.caption('Saved cases and current ledger balances. Source potential and confirmed amounts are separate measures and must not be added together.')

    exposure, progress, priorities = st.tabs(['Exposure analysis', 'Case progress', 'Review priorities'])
    with exposure:
        st.subheader('Potential underbilling by invoice month')
        if model['monthly']:
            chart = pd.DataFrame([{'Invoice month': row['month'], 'Potential underbilling (USD)': float(row['potential_loss'])} for row in model['monthly']])
            st.bar_chart(chart, x='Invoice month', y='Potential underbilling (USD)', color='#0f766e')
            st.caption('Invoice dates, rather than detection or recovery dates. Months without candidates between the first and last observed candidate month show zero.')
        else:
            st.info('No dated underbilling candidates match these filters.')
        left, right = st.columns(2)
        with left:
            _concentration(model['customers'], 'Customers with the largest potential amounts', 'Customer')
        with right:
            _concentration(model['products'], 'Products with the largest potential amounts', 'SKU')
        with st.expander('Current candidate detail'):
            if model['candidates']:
                st.dataframe(pd.DataFrame([{
                    'Invoice': row['invoice_id'], 'Invoice line': row['invoice_line_id'],
                    'Invoice date': row['invoice_date'], 'Customer': row['customer_name'], 'SKU': row['sku'],
                    'Quantity': row['quantity'], 'Agreed unit price': f"${row['agreed_net_unit_price']:,.4f}",
                    'Billed unit price': f"${row['invoiced_net_unit_price']:,.4f}",
                    'Potential underbilling': _usd(row['potential_loss']),
                } for row in model['candidates']]), hide_index=True, width='stretch')
            else:
                st.caption('No current candidates match these filters.')

    with progress:
        a, b, c = st.columns(3)
        a.metric('Active unassigned cases', model['active_unassigned'])
        b.metric('Active cases aged 30+ days', model['active_aged_30_days'])
        c.metric('Net recovery / confirmed', f"{model['recovery_percent']:.1f}%" if model['recovery_percent'] is not None else 'Not applicable')
        left, right = st.columns(2)
        with left:
            st.subheader('Saved case status')
            st.bar_chart(pd.DataFrame([{'Status': row['status'], 'Cases': row['cases']} for row in model['status_breakdown']]),
                         x='Status', y='Cases', color='#0f766e')
        with right:
            st.subheader('Active case age')
            st.bar_chart(pd.DataFrame([{'Age band': row['age_band'], 'Cases': row['cases']} for row in model['active_aging']]),
                         x='Age band', y='Cases', color='#475569', sort=False)
        st.caption('Active means open, investigating or confirmed. Age uses elapsed UTC calendar days since the case was saved; it is not an SLA or invoice aging measure.')
        st.dataframe(pd.DataFrame([{
            'Status': row['status'], 'Cases': row['cases'], 'Saved potential': _usd(row['potential_loss']),
            'Confirmed amount': _usd(row['confirmed_amount']), 'Net recorded recoveries': _usd(row['net_recovered']),
            'Confirmed outstanding': _usd(row['confirmed_outstanding']),
        } for row in model['status_breakdown']]), hide_index=True, width='stretch')
        st.text(f"Outstanding on resolved cases: {_usd(model['closed_outstanding'])}. Closure does not count that balance as recovered.")

    with priorities:
        st.subheader('Largest active balances to review')
        st.caption('Ranked by potential underbilling for unconfirmed cases and confirmed outstanding for confirmed cases. Amount bases are shown separately; this is a review order, not a prediction of recoverability. Equal amounts put older cases first.')
        if model['priorities']:
            st.dataframe(pd.DataFrame([{
                'Invoice line': row['invoice_line_id'], 'Customer': row['customer_name'], 'Status': row['status'],
                'Owner': row['owner'], 'Case age (days)': row['age_days'], 'Amount basis': row['amount_basis'],
                'Review amount': _usd(row['review_amount']),
            } for row in model['priorities']]), hide_index=True, width='stretch')
            st.caption('Top 10 active cases. Copy an invoice line and search for it in Investigations to review its evidence and take action. Fully recovered confirmed cases remain available for closure review at a zero balance.')
        else:
            st.info('No active cases match these filters. Use Investigations to run detection or inspect completed cases.')
