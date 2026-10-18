"""Streamlit upload view; validation and persistence live in separate services."""
import csv
import hashlib
import io
import logging
import zipfile
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st
from marginguard.imports import ImportRejected, MigrationRequired, commit_upload, recent_imports, validate_upload
from marginguard.validation import CONTRACTS


def _examples_zip(path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(Path(path).glob('*.csv')):
            archive.writestr(file.name, file.read_bytes())
    return output.getvalue()


def _issues(report):
    records = [asdict(x) for x in report.issues]
    st.error(f'{len(records)} validation issue(s). Correct the files and validate again.')
    st.dataframe(pd.DataFrame(records[:100]), width='stretch', hide_index=True)
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['file_name', 'row', 'column', 'code', 'message'])
    for record in records:
        # Avoid spreadsheet formulas in exported error text and filenames.
        writer.writerow([("'"+str(v)) if str(v).lstrip().startswith(('=', '+', '-', '@')) else v for v in record.values()])
    st.download_button('Download validation report', output.getvalue().encode('utf-8-sig'), 'validation_errors.csv', 'text/csv')


def render_upload(engine, tenant, examples_dir):
    st.subheader('Upload Data')
    st.write('Upload related CSV files together, validate them, then import the accepted records.')
    st.caption('USD only • UTF-8 CSV • Maximum 5 MiB and 10,000 records per file • New document IDs only')
    with st.expander('File names and required columns'):
        for name, columns in CONTRACTS.items():
            st.write(f'**{name}.csv:** ' + ', '.join(columns))
        st.write('An optional tenant_id column must match the configured organization. Customers and products must already exist or be included in this upload. Dates use YYYY-MM-DD; prices are net of approved discounts and exclude tax.')
    a, b = st.columns(2)
    with a:
        st.download_button('Download valid sample files', _examples_zip(Path(examples_dir)/'valid'), 'valid_import_example.zip', 'application/zip')
    with b:
        st.download_button('Download invalid sample files', _examples_zip(Path(examples_dir)/'invalid'), 'invalid_import_example.zip', 'application/zip')
    uploaded = st.file_uploader('Choose CSV files', type=['csv'], accept_multiple_files=True)
    inputs = [(f.name, f.getvalue()) for f in uploaded]
    signature = hashlib.sha256(tenant.encode()+b'\0'+b''.join(hashlib.sha256(n.encode()+b'\0'+v).digest() for n,v in inputs)).hexdigest()
    if inputs and st.button('Validate files', type='primary'):
        st.session_state.pop('import_receipt', None)
        try:
            with engine.connect() as conn:
                report = validate_upload(conn, tenant, inputs)
            st.session_state['import_validation'] = (signature, report)
        except MigrationRequired:
            st.error('Apply migration 002: run python scripts/migrate_db.py from your project terminal.')
        except Exception as exc:
            logging.getLogger(__name__).error('Upload validation connection failure (%s)', type(exc).__name__)
            st.error('Cannot validate against the database. Check the database connection and migration 002.')
    saved = st.session_state.get('import_validation')
    if saved and saved[0] == signature:
        report = saved[1]
        if report.issues:
            _issues(report)
        else:
            st.success(f'Validation passed: {sum(len(f.rows) for f in report.files)} records in {len(report.files)} files.')
            for f in report.files:
                with st.expander(f'{f.file_name}: {len(f.rows)} records'):
                    st.dataframe(pd.DataFrame([{k:str(v) for k,v in row.items() if k!='_source_row'} for row in f.rows[:20]]), width='stretch', hide_index=True)
            st.metric('Potential underbilling in these invoice lines', f"${sum((Decimal(x['potential_loss']) for x in report.preview),Decimal('0')):,.2f}")
            if report.preview:
                st.dataframe(pd.DataFrame(report.preview), width='stretch', hide_index=True)
            already_committed = st.session_state.get('import_receipt', (None,))[0] == signature
            if st.button('Import validated files', disabled=already_committed, type='primary'):
                try:
                    receipt = commit_upload(engine, tenant, inputs)
                    st.session_state['import_receipt'] = (signature, receipt)
                except ImportRejected as exc:
                    st.session_state['import_validation'] = (signature, exc.report)
                    _issues(exc.report)
                except Exception as exc:
                    logging.getLogger(__name__).error('Import rolled back (%s)', type(exc).__name__)
                    st.error('The import could not be committed. No records from this upload were saved. Check the database connection, then validate again.')
            receipt = st.session_state.get('import_receipt')
            if receipt and receipt[0] == signature:
                st.success('Import complete. Open Dashboard to see the updated totals.')
                st.dataframe(pd.DataFrame(receipt[1]), width='stretch', hide_index=True)
    st.subheader('Recent imports')
    try:
        with engine.connect() as conn:
            history = recent_imports(conn, tenant)
        if history:
            st.dataframe(pd.DataFrame(history), width='stretch', hide_index=True)
        else:
            st.caption('No CSV imports yet. Phase 1 demo seeds are not listed here.')
    except Exception:
        st.caption('Import history becomes available after migration 002 and a working database connection.')
