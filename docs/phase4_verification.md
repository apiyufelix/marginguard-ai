# Phase 4 verification record

Date: 2026-10-17.

## Automated checks

All **62 tests passed** in the development harness: **45 unit/fixture tests** and **17 database integration tests**. The normal local command skips the integration tests when `MARGINGUARD_TEST_DATABASE_URL` is absent.

The 14 new reporting tests cover exact amounts, pricing reconciliation, missing evidence and lineage, status-aware recommendations, resolved cases with outstanding balances, ledger mismatches, reversal effects, decimal JSON output, exclusion of private request metadata, HTML escaping, filtered CSV contents, formula-like text, absent values, safe filenames, aware timestamps and nonmutation of source objects.

The existing database tests continue to cover imports, idempotent detection, case transitions, confirmation and recovery limits, append-only activity, stale versions, reversals and tenant-scoped case access. Full-fixture detection still matches 116 findings and $69,506.40 before the additional Phase 2 sample import.

## Streamlit workflow

Streamlit AppTest verified the new summary section and all three download controls on the existing investigation page. It also completed the prior workflow: sample upload, detection, ownership, note, investigation, confirmation, partial recovery, cap rejection, resolution, rescan, reversal/correction and persistence in a fresh session.

Download bytes and content were checked through the pure reporting tests. Browser-based file saving was not automated. A local browser executable was unavailable for visual rendering of the HTML report; its structure, escaping and self-contained content were checked programmatically. Open the included synthetic HTML sample locally for a final visual check in your browser.

## Environment and limits

Python 3.12.14, pandas 2.3.3, SQLAlchemy 2.1.5, psycopg 3.3.6 and Streamlit 1.66.0. Database checks used PGlite embedded PostgreSQL through its socket adapter; prepared statements were disabled for test connections. No new native Windows PostgreSQL or Python 3.13 run was performed in this environment.

There are no Phase 4 migrations. Reports are snapshots of existing records, and recorded recoveries are not independently verified bank settlements. Verified identity, production permissions, hosted tenant isolation and concurrent production load remain outside this verification.
