# Phase 2 implementation map

| File | Responsibility |
|---|---|
| src/marginguard/validation.py | Pure CSV parser, typed contracts, relational reconciliation and exposure preview |
| src/marginguard/imports.py | Tenant-filtered context queries, transaction lock, final validation, inserts and lineage |
| src/marginguard/upload_page.py | Upload selection, validation feedback, preview, explicit commit and history |
| sql/002_import_lineage.sql | Additive source and lineage storage |
| scripts/migrate_db.py | Version-aware migration runner |
| tests/test_validation.py | Invalid inputs, tenant mismatch, decimal precision, quantities and relationships |
| tests/test_import_database.py | Opt-in transaction, lineage, duplicate and tenant-context integration checks |

Streamlit file inputs are read using getvalue(); no UploadedFile objects are retained in global caches. Engine instances alone use st.cache_resource. Validation reports remain in the user's session and are tied to the selected filenames, bytes and configured tenant. Import always revalidates against current database contents; a previous successful preview cannot authorize stale writes.

All SQL values are bound parameters. Dynamic table/column names come solely from the fixed application contracts. Source keys are never interpolated into SQL. Raw and normalized source records are linked by composite tenant/batch/row foreign keys. SHA-256 prevents exact re-uploads while document-key checks catch reordered or reformatted files containing existing records.

Sources consulted: https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader and https://docs.sqlalchemy.org/en/20/tutorial/dbapi_transactions.html .
