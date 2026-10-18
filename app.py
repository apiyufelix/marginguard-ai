import logging
import os
from pathlib import Path

import streamlit as st
from marginguard.db import get_engine
from marginguard.upload_page import render_upload
from marginguard.cases_page import render_investigations
from marginguard.dashboard_page import render_dashboard

st.set_page_config(page_title='MarginGuard AI', layout='wide')
st.title('MarginGuard AI')
st.caption('Local development • Fictional distributor • USD')
st.info('Potential underbilling requires investigation. It is not confirmed loss or recovered cash.')

@st.cache_resource
def engine():
    return get_engine()

try:
    db = engine()
    tenant = os.getenv('DEMO_TENANT_ID', 'demo-distributor')
    section = st.sidebar.radio('Navigation', ['Dashboard', 'Upload Data', 'Investigations'])
    if section == 'Upload Data':
        render_upload(db, tenant, Path(__file__).resolve().parent/'data/import_examples')
    elif section == 'Investigations':
        render_investigations(db,tenant)
    else:
        render_dashboard(db,tenant)
except Exception as exc:
    logging.getLogger(__name__).error('Dashboard unavailable (%s)', type(exc).__name__)
    st.error('Database unavailable or not initialized. Check your .env connection and database setup.')
