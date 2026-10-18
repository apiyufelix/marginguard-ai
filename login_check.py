"""Standalone OIDC smoke check. Does not connect to the business database."""
import streamlit as st

st.set_page_config(page_title='MarginGuard AI — Sign-in check', layout='centered')
st.title('MarginGuard AI')
st.caption('Google sign-in check')
st.info('This page tests sign-in only. Company data and permissions are not connected yet.')

if not st.user.is_logged_in:
    st.button('Sign in with Google', on_click=st.login, type='primary')
    st.stop()

st.success('Google sign-in succeeded.')
st.text('Signed in as: ' + str(st.user.get('name') or 'Google user'))
st.button('Sign out', on_click=st.logout)
