import logging
from pathlib import Path

import streamlit as st
from marginguard.db import get_engine
from marginguard.access import AccessDenied, CompanyEngine, google_identity, register_identity, companies
from marginguard.access_page import render_access
from marginguard.upload_page import render_upload
from marginguard.cases_page import render_investigations
from marginguard.dashboard_page import render_dashboard

st.set_page_config(page_title='MarginGuard AI', layout='wide')
st.title('MarginGuard AI')
st.caption('Development • Fictional distributor • USD')

@st.cache_resource
def engine():
    # Only the pool is shared. User/company scopes are never cached.
    return get_engine()

if not st.user.is_logged_in:
    st.session_state.clear()
    st.write('Sign in to access your company workspace.')
    st.button('Sign in with Google',on_click=st.login,type='primary')
    st.stop()

st.sidebar.button('Sign out',on_click=st.logout)
try:
    identity = google_identity(st.user)
    db = engine()
    account = register_identity(db,identity)
    options = companies(db,account['user_id'])
except AccessDenied as exc:
    st.session_state.clear()
    st.error(str(exc))
    st.stop()
except Exception as exc:
    logging.getLogger(__name__).error('Account setup unavailable (%s)',type(exc).__name__)
    st.error('Account setup is unavailable. Check your database connection and apply migrations through 005.')
    st.stop()

st.sidebar.text('Signed in as: '+account['display_name'])
st.sidebar.caption('MarginGuard account ID')
st.sidebar.code(str(account['user_id']),language=None)
if not options:
    st.session_state.clear()
    st.info('Your account is ready, but no company membership has been granted. Share your MarginGuard account ID with your company administrator.')
    st.stop()

lookup = {x['tenant_id']:x for x in options}
if st.session_state.get('auth_company') not in lookup:
    st.session_state.pop('auth_company',None)
tenant = st.sidebar.selectbox('Company',list(lookup),key='auth_company',format_func=lambda key:lookup[key]['name'])
role = lookup[tenant]['role']
scope = (str(account['user_id']),tenant,role)
if st.session_state.get('_access_scope') != scope:
    for key in list(st.session_state):
        if key != 'auth_company':
            del st.session_state[key]
    st.session_state['_access_scope'] = scope
st.sidebar.text('Role: '+role.title())
workspace = CompanyEngine(db,account['user_id'],tenant,identity.expires)
sections = ['Dashboard','Investigations']
if role in ('analyst','admin'):
    sections.append('Upload Data')
if role == 'admin':
    sections.append('Company access')
section = st.sidebar.radio('Navigation',sections)
st.info('Potential underbilling requires investigation. It is not confirmed loss or recovered cash.')
try:
    if section == 'Upload Data':
        render_upload(workspace, tenant, Path(__file__).resolve().parent/'data/import_examples')
    elif section == 'Investigations':
        render_investigations(workspace,tenant,can_write=role in ('analyst','admin'),actor_name=account['display_name'])
    elif section == 'Company access':
        render_access(workspace,tenant)
    else:
        render_dashboard(workspace,tenant)
except AccessDenied as exc:
    st.error(str(exc))
except Exception as exc:
    logging.getLogger(__name__).error('Workspace unavailable (%s)', type(exc).__name__)
    st.error('The workspace could not load. Refresh and check the database connection if the problem continues.')
