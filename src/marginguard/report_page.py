"""Read-only decision support and case downloads."""
from datetime import datetime,timezone
import streamlit as st
from marginguard.reporting import explain_case,filename,html_report,json_report


def render_case_support(case):
    st.subheader('Case summary and next checks')
    st.caption('Rule-based explanations from saved evidence and case activity. Suggested causes require investigation.')
    analysis=explain_case(case)
    summary,checks,reports=st.tabs(['Summary','Suggested checks','Reports'])
    with summary:
        st.text(analysis['summary'])
        st.text(analysis['review_summary'])
        st.caption(analysis['lineage_summary'])
        for issue in analysis['quality_issues']:
            st.warning(issue)
    with checks:
        for number,item in enumerate(analysis['recommended_checks'],1):
            st.text(f'{number}. {item}')
        if analysis['possible_explanations']:
            with st.expander('Possible explanations to verify'):
                st.caption('These are hypotheses. The saved evidence does not establish the cause.')
                for item in analysis['possible_explanations']:
                    st.text('• '+item)
    with reports:
        generated=datetime.now(timezone.utc)
        st.write('Download the selected case with its current review state, evidence and activity history.')
        a,b=st.columns(2)
        with a:
            st.download_button('Download case report (HTML)',data=html_report(case,generated),
                file_name=filename(case,'html'),mime='text/html',on_click='ignore',
                key=f"case_html:{case['finding_id']}:{case['version']}")
        with b:
            st.download_button('Download case data (JSON)',data=json_report(case,generated),
                file_name=filename(case,'json'),mime='application/json',on_click='ignore',
                key=f"case_json:{case['finding_id']}:{case['version']}")
        st.caption('The HTML report opens in a browser and can be printed. Reports capture the case version shown on this page; refresh to include later changes.')
