# Phase 5 verification

Verified: 2026-10-18 UTC.

## Automated tests

All **80 tests passed** in the development harness: **59 unit/fixture tests** and **21 PostgreSQL integration tests**. The default local test command skips the integration tests unless `MARGINGUARD_TEST_DATABASE_URL` is configured for a disposable database.

The 14 new pure analytic tests cover exact independent source/case totals, invoice-cohort filtering, inclusive boundaries, missing dates, monthly gaps, duplicate customer names and SKU labels with distinct IDs, concentration shares, closed balances, unconfirmed recovery percentages, UTC age bands, remaining-balance priorities, closure work, missing dimensions, empty selections, invalid inputs, deterministic top-10 ranking and source-object nonmutation.

Four new database tests verify that the dashboard reads the existing case/source data without changing case versions or events, excludes another organization's data, keeps reversals and resolved balances correct, and filters cases by their captured invoice date rather than case-creation date. Existing import, workflow, report and full-fixture regression tests also pass.

## Streamlit workflow

AppTest verified:

1. The initial all-customer dashboard shows 116 candidates and $69,506.40.
2. All three dashboard tabs and chart controls render without application errors.
3. A customer selection matches an independent SQL aggregate.
4. A date range outside the fixture gives zero candidates; clearing it restores the full totals.
5. Phase 2 sample upload and import still work.
6. Detection, report controls, ownership, notes, confirmation, partial recovery, over-recovery rejection, resolution, rescan, reversal/correction and persistence still work.
7. Returning to Dashboard shows 118 candidates and $69,576.40 after the sample import, with the saved $20 confirmation, corrected $20 net recovery and $0 outstanding reflected separately.

These are component and workflow checks. Browser pixel rendering, download dialogs and mobile layout were not separately exercised for this update. Review the charts on the user's local browser as part of the setup walkthrough.

## Environment and limits

Python 3.12.14, pandas 2.3.3, SQLAlchemy 2.1.5, psycopg 3.3.6 and Streamlit 1.66.0. Database checks used PGlite embedded PostgreSQL through its socket adapter, with prepared statements disabled for test connections. The normal application uses its existing PostgreSQL engine configuration.

This environment did not run native Windows PostgreSQL or Python 3.13. No new migration or dependency is required. Concurrent production load, authenticated tenant membership, bank settlement and production permissions were not validated.
