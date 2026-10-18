# MarginGuard AI — Phase 2 update

This update adds a CSV upload page, typed validation, duplicate detection, atomic imports, original-file retention, row lineage and import history. It extends your working Phase 1 database without replacing the demo records. Existing .env and virtual environment are not included in the update ZIP.

## 1. Copy the update into your project

In the terminal running Streamlit, press Ctrl+C. Extract `MarginGuard_AI_Phase2_Update.zip`. Open the extracted `MarginGuard_AI_Phase2_Update` folder and copy **its contents** into:

`C:\Users\apiyu\OneDrive\Lecture Notes\Application\MarginGuard AI`

Merge matching folders and replace `app.py` when prompted. Copy all supplied folders, not just app.py. At the project root, `app.py`, `PHASE2_SETUP.md` and the existing `.env` should be together. Your database credentials remain in your existing .env.

## 2. Apply the additive database migration

Open the existing project in VS Code. In its terminal:

```powershell
.\.venv\Scripts\python.exe scripts/migrate_db.py
```

Migration 002 adds import metadata, a row-lineage table and nullable lineage columns on six existing tables. Phase 1 seed records remain unchanged. The runner recognizes an already-applied 002 migration and exits safely. Do not run init_db.py again.

## 3. Check and launch

The libraries are the same as Phase 1; the update requires Streamlit 1.50 or newer for current table sizing. Refresh the requirements before running:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The normal test run includes 24 passing unit/fixture tests and five skipped database integration tests unless a dedicated test URL is configured. The database suite creates and drops an isolated random schema and is intended for a disposable test database; do not point it at production. See `tests/test_import_database.py`.

Choose **Upload Data** in the sidebar. Your Dashboard initially retains $69,506.40 across 116 invoice lines.

## 4. Try an invalid upload first

Use the four CSVs from `data/import_examples/invalid` together, or download and extract the invalid example ZIP from the page. Select **Validate files**.

Expected: three validation issues—an unknown product, an invoice before its order date, and a billed quantity above the ordered quantity. No import is offered and no database records are written. Download the error report to inspect the locations.

## 5. Import the valid sample

Remove the invalid files from the uploader. Select all four files in `data/import_examples/valid` together:

- orders.csv
- order_lines.csv
- invoices.csv
- invoice_lines.csv

Select **Validate files**. Expected: 11 records, no errors, and $70.00 of potential underbilling across two invoice lines. The sample uses existing demo customers C001/C002 and products P001/P002/P003. It includes one correctly billed order line split across two invoice rows.

Select **Import validated files** once. A receipt and four committed import entries should appear. Switch to Dashboard:

| Measure | Before sample | After one import |
|---|---:|---:|
| Potential underbilling | $69,506.40 | $69,576.40 |
| Flagged invoice lines | 116 | 118 |
| Orders in database | 500 | 502 |
| Order lines in database | 1,231 | 1,234 |
| Invoice lines in database | 1,313 | 1,317 |

Validate the same files again. They should be rejected as duplicates, with the totals unchanged. Identical file hashes and existing document IDs are both checked. This importer adds new records; changing an existing order or invoice requires a future correction/versioning workflow.

## 6. Optional SQL verification in pgAdmin

Run against the marginguard database:

```sql
SELECT version FROM schema_migrations ORDER BY version;
SELECT count(*), sum(potential_loss)
FROM underbilling_candidates
WHERE tenant_id = 'demo-distributor';
SELECT file_name, dataset, row_count, status, imported_at
FROM import_batches
WHERE tenant_id = 'demo-distributor'
ORDER BY imported_at DESC;
```

Expect migrations 001/002, 118 candidates, total 69576.40 and four committed file receipts after one valid sample import.

## Supported input contract

File names must match the dataset: customers.csv, products.csv, orders.csv, order_lines.csv, invoices.csv, invoice_lines.csv. Upload at most one of each at a time; related files may be selected in any order. Column names are listed on the upload page and in `src/marginguard/validation.py`. Required columns must all be present; unexpected columns are rejected. An optional tenant_id column must match the organization configured by the app. The importer never uses file contents to choose an organization.

Use UTF-8 (BOM allowed), comma delimiters, ISO dates, nonnegative prices without symbols or separators, and whole positive quantities. Prices accept at most four decimal places and ten integer digits. IDs remain text so leading zeros survive. File limit: 5 MiB and 10,000 data records each. Only USD data is supported by the current organization/schema contract.

Customer and product references must exist already or be included in the same upload. Invoice lines must match their invoice and order line to the same order. Posted quantities across existing and uploaded slices cannot exceed the ordered quantity. Void invoices do not contribute to billed quantities or underbilling exposure. Confirmed financial loss and recoveries are still separate future workflows.

## Implementation and limits

Validation is read-only. On import, the service re-parses and revalidates the uploaded bytes inside one transaction while holding a tenant-scoped advisory lock. It stores original CSV bytes, their SHA-256 hash, normalized row snapshots and source pointers, then appends business records. A failed import rolls back the entire bundle, including receipts. Staged/validated states occur inside that transaction; only committed receipts survive. Rejected upload attempts are displayed, not persisted as audit events.

The original CSVs remain in PostgreSQL for this local prototype. A hosted product should use private object storage, retention controls, verified tenant identity, least-privilege database accounts and authorization/row-security tests. Existing demo records predate source lineage and retain null pointers. This update does not add authentication, an arbitrary column mapper, Excel support, persisted findings, or a case investigation UI.

The portfolio-sized validator currently loads tenant context for the six supported tables. Production scale should query only the referenced IDs and aggregate quantities in SQL. The advisory lock coordinates this import service; it does not protect against unrelated direct SQL writers or replace authenticated tenant isolation.
