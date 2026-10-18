"""Evidence and case workflow UI for the local single-user portfolio application."""
from decimal import Decimal
import json
import logging
from uuid import uuid4

import pandas as pd
import streamlit as st
from marginguard.cases import (
    CaseMigrationRequired, active_recoveries, add_note, assign_owner,
    change_status, get_case, list_cases, record_recovery, reverse_recovery,
    run_detection, summarize,
)
from marginguard.workflow import ALLOWED_TRANSITIONS, CasePolicyError
from marginguard.reporting import queue_csv
from marginguard.report_page import render_case_support


def _action_key(kind,case):
    name=f"action:{kind}:{case['finding_id']}:{case['version']}"
    if name not in st.session_state:
        st.session_state[name]=str(uuid4())
    return st.session_state[name]


def _save(call):
    try:
        result=call()
        st.session_state['case_notice']='Action was already saved.' if result.get('replayed') else 'Case updated.'
        st.rerun()
    except CasePolicyError as exc:
        st.error(str(exc))
    except Exception as exc:
        logging.getLogger(__name__).error('Case action failed (%s)',type(exc).__name__)
        st.error('The action could not be saved. Refresh the page and review the current case before trying again.')


def render_case_metrics(conn,tenant):
    try:
        summary=summarize(list_cases(conn,tenant))
    except CaseMigrationRequired:
        st.caption('Apply migration 003 to enable investigation tracking.')
        return
    st.subheader('Investigation progress')
    a,b,c,d=st.columns(4)
    a.metric('Saved findings',summary['saved_findings'])
    b.metric('Confirmed amount',f"${summary['confirmed_amount']:,.2f}")
    c.metric('Net recorded recoveries',f"${summary['net_recovered']:,.2f}")
    d.metric('Confirmed outstanding',f"${summary['confirmed_outstanding']:,.2f}")


def render_investigations(engine,tenant,*,can_write=True,actor_name=None):
    st.subheader('Investigations')
    st.write('Save the latest underbilling candidates, review their evidence, and track the decisions and recoveries.')
    notice=st.session_state.pop('case_notice',None)
    if notice:
        st.success(notice)
    try:
        with engine.connect() as conn:
            cases=list_cases(conn,tenant)
    except CaseMigrationRequired:
        st.error('Run python scripts/migrate_db.py from your project terminal to apply migration 003.')
        return
    if can_write and st.button('Run detection',type='primary'):
        try:
            outcome=run_detection(engine,tenant)
            st.success(f"Detection complete: {outcome['created']} new findings; {outcome['already_saved']} already saved.")
            with engine.connect() as conn:
                cases=list_cases(conn,tenant)
        except Exception as exc:
            logging.getLogger(__name__).error('Detection failed (%s)',type(exc).__name__)
            st.error('Detection could not complete. Check the database and migration 003.')
    if not cases:
        st.info('No saved findings yet. Run detection to create the first review queue.')
        return
    summary=summarize(cases)
    a,b,c,d=st.columns(4)
    a.metric('Saved findings',summary['saved_findings'])
    b.metric('Confirmed amount',f"${summary['confirmed_amount']:,.2f}")
    c.metric('Net recorded recoveries',f"${summary['net_recovered']:,.2f}")
    d.metric('Confirmed outstanding',f"${summary['confirmed_outstanding']:,.2f}")
    left,right=st.columns(2)
    status=left.selectbox('Filter by status',['All statuses',*ALLOWED_TRANSITIONS])
    query=right.text_input('Search invoice, customer or SKU').strip().casefold()
    shown=[c for c in cases if (status=='All statuses' or c['status']==status) and (not query or query in ' '.join(str(c['evidence'].get(k,'')) for k in ('invoice_id','invoice_line_id','customer_name','sku')).casefold())]
    if not shown:
        st.info('No findings match these filters.')
        return
    st.dataframe(pd.DataFrame([{
        'Invoice line':c['invoice_line_id'],'Customer':c['evidence'].get('customer_name',''),
        'Potential underbilling':float(c['potential_loss']),'Status':c['status'],
        'Owner':c['assigned_to'] or 'Unassigned',
    } for c in shown]),width='stretch',hide_index=True,column_config={
        'Potential underbilling':st.column_config.NumberColumn(format='$%.2f')})
    st.download_button('Download filtered cases (CSV)',data=queue_csv(shown),
        file_name='MarginGuard_filtered_cases.csv',mime='text/csv',on_click='ignore',key='filtered_case_download')
    lookup={c['finding_id']:c for c in shown}
    if st.session_state.get('selected_finding') not in lookup:
        st.session_state.pop('selected_finding',None)
    selected=st.selectbox('Select a finding',list(lookup),key='selected_finding',
        format_func=lambda key:f"{lookup[key]['invoice_line_id']} · ${lookup[key]['potential_loss']:,.2f} · {lookup[key]['status']}")
    with engine.connect() as conn:
        case=get_case(conn,tenant,selected)
    evidence=case['evidence']
    st.subheader(f"Evidence: {case['invoice_line_id']}")
    st.write(f"**Customer:** {evidence.get('customer_name','')} · **SKU:** {evidence.get('sku','')} · **Status:** {case['status']}")
    st.text(f"{evidence['quantity']} units × (${Decimal(evidence['agreed_net_unit_price']):,.4f} agreed − ${Decimal(evidence['invoiced_net_unit_price']):,.4f} billed) = ${case['potential_loss']:,.2f} potential underbilling")
    st.caption('Evidence is the snapshot captured when this rule first saved the finding. Current source comparisons remain visible on Dashboard.')
    with st.expander('Source documents and captured evidence'):
        st.json(evidence)
    a,b,c=st.columns(3)
    a.metric('Confirmed for this case',f"${case['confirmed_amount']:,.2f}" if case['confirmed_amount'] is not None else 'Not confirmed')
    b.metric('Net recorded recoveries',f"${case['net_recovered']:,.2f}")
    if case['confirmed_amount'] is not None:
        c.metric('Confirmed outstanding',f"${case['confirmed_amount']-case['net_recovered']:,.2f}")
    render_case_support(case)
    if can_write:
        actor=actor_name
        if actor is None:
            actor=st.text_input('Activity author',value='Felix Apiyu',key='case_activity_author',max_chars=128)
        else:
            st.text('Activity author: '+actor)
        st.caption('Recovery entries should reference supporting financial records. Assigned owner is a workflow label.')
        version=case['version']; finding=case['finding_id']
        with st.expander('Owner and notes'):
            with st.form(f'owner:{finding}:{version}'):
                owner=st.text_input('Assigned owner',value=case['assigned_to'] or '',max_chars=128)
                if st.form_submit_button('Save owner'):
                    _save(lambda:assign_owner(engine,tenant,finding,owner,actor,version,_action_key('owner',case)))
            with st.form(f'note:{finding}:{version}'):
                note=st.text_area('Investigation note',max_chars=4000)
                if st.form_submit_button('Add note'):
                    _save(lambda:add_note(engine,tenant,finding,note,actor,version,_action_key('note',case)))
        with st.expander('Change status',expanded=True):
            target=st.selectbox('Next status',ALLOWED_TRANSITIONS[case['status']],key=f'target:{finding}:{version}')
            with st.form(f'status:{finding}:{version}:{target}'):
                confirmation=None
                if case['status']=='investigating' and target=='confirmed':
                    confirmation=st.text_input('Confirmed amount (USD)',value=str(case['potential_loss']))
                    st.caption('Confirm the amount supported by your review. It may be lower than the potential discrepancy.')
                close_with_balance=False
                if case['status']=='confirmed' and target=='resolved' and case['net_recovered']<case['confirmed_amount']:
                    close_with_balance=st.checkbox('Close with an unrecovered balance')
                    st.caption('Explain why the remaining balance is being closed. Closing a case does not count that balance as recovered.')
                reason=st.text_area('Reason for status change',max_chars=2000)
                if st.form_submit_button('Save status'):
                    _save(lambda:change_status(engine,tenant,finding,target,reason,actor,version,_action_key('status:'+target,case),confirmation,close_with_balance))
        if case['status']=='confirmed':
            with st.expander('Record or reverse a recovery'):
                remaining=case['confirmed_amount']-case['net_recovered']
                if remaining>0:
                    with st.form(f'recovery:{finding}:{version}'):
                        amount=st.text_input('Recovery amount (USD)',value='0.00')
                        reference=st.text_input('Recovery reference',max_chars=128)
                        recovery_note=st.text_area('Recovery note',max_chars=2000)
                        if st.form_submit_button('Record recovery'):
                            _save(lambda:record_recovery(engine,tenant,finding,amount,reference,recovery_note,actor,version,_action_key('recovery',case)))
                choices=active_recoveries(case)
                if choices:
                    recovery_map={r['event_id']:r for r in choices}
                    original=st.selectbox('Recovery to reverse',list(recovery_map),key=f'reverse_select:{finding}:{version}',
                        format_func=lambda key:f"{recovery_map[key]['details'].get('reference','')} · ${recovery_map[key]['amount']:,.2f}")
                    with st.form(f'reverse:{finding}:{version}'):
                        reversal_note=st.text_area('Reversal reason',max_chars=2000)
                        if st.form_submit_button('Reverse selected recovery'):
                            _save(lambda:reverse_recovery(engine,tenant,finding,original,reversal_note,actor,version,_action_key('reverse',case)))
    else:
        st.info('Viewer access: case changes and detection are available to Analysts and Admins.')
    st.subheader('Case activity')
    history=[]
    for event in case['events']:
        details={k:v for k,v in event['details'].items() if k!='request_fingerprint'}
        history.append({'Time':event['created_at'],'Action':event['event_type'],'Author':event['actor'],
                        'Amount':str(event['amount']) if event['amount'] is not None else '',
                        'Details':json.dumps(details,ensure_ascii=False)})
    st.dataframe(pd.DataFrame(history),width='stretch',hide_index=True)
