"""Company membership administration for authenticated administrators."""
import pandas as pd
import streamlit as st
from marginguard.access import membership_list, set_membership, ROLES


def render_access(engine, tenant):
    st.subheader('Company access')
    members = membership_list(engine,tenant)
    st.dataframe(pd.DataFrame(members),hide_index=True,width='stretch')
    st.caption('People must sign in once to create their account, then share their MarginGuard account ID with you. Email does not grant access automatically.')
    with st.form('company_membership'):
        target = st.text_input('MarginGuard account ID (UUID)')
        role = st.selectbox('Company role',list(ROLES))
        active = st.checkbox('Membership active',value=True)
        if st.form_submit_button('Save membership'):
            try:
                changed = set_membership(engine,tenant,target,role,active)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success('Membership saved. Refresh the page to see the updated list.' if changed else 'Membership is unchanged.')
