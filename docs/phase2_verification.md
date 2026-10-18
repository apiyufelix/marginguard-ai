# Phase 2 verification record

Date: 2026-10-17.

- 24 unit and fixture tests passed, including decimal precision, leading-zero IDs, BOMs, malformed data, unknown references, tenant mismatch, duplicate keys, dates, split quantities and void invoices.
- Five database integration tests passed: atomic valid import and lineage, cross-tenant reference lookup, an injected write failure with complete rollback, rejection without writes, and commit-time revalidation of a stale preview.
- The migration runner applied 002 after 001 and safely recognized a second run.
- Streamlit AppTest exercised the dashboard and upload page. File selection was supplied by test UploadedFile stand-ins; validation/import buttons and navigation were exercised through AppTest.
- Baseline dashboard: 116 candidates, $69,506.40.
- Invalid sample: three reported issues; no commit button.
- Valid sample preview: 11 records, two underbilling cases, $70.00.
- Valid import: four receipts; duplicate validation rejected the same source files.
- Resulting dashboard: 118 candidates, $69,576.40.

Environment: Python 3.12.14, pandas 2.3.3, SQLAlchemy 2.1.5, psycopg 3.3.6, Streamlit 1.66.0. Database checks used PGlite's embedded PostgreSQL over its socket adapter with prepared statements disabled in the test connections. This is not a native Windows PostgreSQL verification or a concurrent-load test. Production application code uses the normal PostgreSQL driver/engine configuration.

The delivered integration tests can run against a disposable native PostgreSQL database via MARGINGUARD_TEST_DATABASE_URL. Without that variable they skip, while all 24 unit/fixture tests remain runnable. Manual acceptance steps for the user's local PostgreSQL database are in PHASE2_SETUP.md. No claim of production tenant isolation, authentication, concurrency performance or SaaS readiness is made.
