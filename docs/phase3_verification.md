# Phase 3 verification record

Date: 2026-10-17.

## Automated checks

All 48 delivered tests passed: 31 unit/fixture tests and 17 database integration tests. The default local run skips the 17 integration tests unless MARGINGUARD_TEST_DATABASE_URL is configured for a disposable test database.

New policy/workflow coverage includes bounded confirmation, exact USD inputs, allowed transitions, explicit closure with a remaining balance, recovery caps, active-reference duplication, idempotent request replay, stale versions, reversals, tenant-scoped case access, append-only events, and rollback when an event insert fails. Existing upload tests continue to pass.

A full-fixture regression imports all six supported CSV datasets for a separate test tenant. Detection produces exactly 116 findings and $69,506.40, matching the synthetic manifest. All those findings contain source batch pointers for the order and invoice rows. This checks both the enriched candidate view and persistence against the complete synthetic dataset, beyond the small case-policy fixtures.

## Streamlit workflow check

Streamlit AppTest exercised:

1. Phase 1 seed loading and migration 003, including a safe second migration run.
2. Existing Phase 2 valid sample upload and import.
3. Saving 118 findings through Run detection.
4. Searching IMP-IL001, assigning an owner and recording a note.
5. Moving open → investigating → confirmed for $20.00.
6. Recording a $10.00 partial recovery, rejecting an additional $11.00, then accepting the remaining $10.00 with a different reference.
7. Resolving the case and rescanning without reopening or duplicating it.
8. Reopening, reversing an original $10.00 receipt, adding a corrected receipt and resolving again.
9. Opening a fresh AppTest session and reading 118 saved findings, $20.00 confirmed, $20.00 net recorded recovery and $0 outstanding from PostgreSQL.

File selection was supplied by UploadedFile stand-ins; the action forms, buttons and navigation ran through AppTest. The full-data test led to simplifying evidence enrichment into one candidate view, avoiding redundant joins.

## Environment and limits

Python 3.12.14, pandas 2.3.3, SQLAlchemy 2.1.5, psycopg 3.3.6, Streamlit 1.66.0. Database checks ran against PGlite embedded PostgreSQL via its socket adapter, with prepared statements disabled in test connections. The application uses the normal PostgreSQL driver configuration.

These checks do not substitute for applying the migration on the user's native Windows PostgreSQL instance. Concurrent-load behavior, verified identity, bank settlement, production permissions and hosted tenant isolation were not tested. The application remains a local portfolio prototype with manual author/owner labels and a recorded recovery ledger.
