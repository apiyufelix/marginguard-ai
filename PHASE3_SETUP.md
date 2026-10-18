# MarginGuard AI — Phase 3: Investigations and Recovery Tracking

This update turns underbilling candidates into durable review cases, with captured evidence, ownership, notes, status transitions and a recovery ledger. Install after your working Phase 2 update.

## 1. Install the update

Stop Streamlit with Ctrl+C. Extract `MarginGuard_AI_Phase3_Update.zip`, open its `MarginGuard_AI_Phase3_Update` folder, then copy all its contents into your existing project:

`C:\Users\apiyu\OneDrive\Lecture Notes\Application\MarginGuard AI`

Merge matching folders and replace matching files. The update contains app.py, new Python modules, migration 003, an updated migration runner, tests and documentation. Your existing .env, Python environment and Phase 1/2 source/data files remain in the project. No additional libraries are required beyond Phase 2.

## 2. Apply migration 003

In your existing VS Code project terminal:

```powershell
.\.venv\Scripts\python.exe scripts/migrate_db.py
```

Expected for a working Phase 2 database:

```text
Migration 002 already applied; no changes needed.
Applied migration 003.
```

The runner safely skips migrations already applied. Migration 003 adds confirmation amounts, case versions and event metadata, widens financial storage, and protects case events against updates/deletes. Do not rerun init_db.py. This migration expects the Phase 1/2 schema and no manually created legacy confirmed cases; any incompatible pre-existing case data should be reviewed rather than silently converted.

## 3. Run checks and launch

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Without MARGINGUARD_TEST_DATABASE_URL, expect 31 passing unit/fixture tests and 17 skipped integration tests (48 total). The integration tests are optional and create/drop isolated schemas in a disposable test database.

Open **Investigations** in the sidebar. Choose **Run detection**. With the Phase 2 valid example already imported, the first scan saves 118 findings. Repeating the scan creates zero additional findings and preserves owners, notes, statuses and recorded recoveries. With only the original Phase 1 data, the first scan saves 116 findings.

Dashboard's candidate scan still reports current source comparisons: $69,576.40 and 118 invoice lines after the valid sample import. Investigation metrics are separate and begin with zero confirmed amounts and recoveries.

## 4. Review the $20 example

The Phase 2 valid sample supplies invoice line `IMP-IL001`:

- Order quantity: 10.
- Agreed net unit price: $20.00.
- Billed net unit price: $18.00.
- Potential underbilling: 10 × ($20 − $18) = $20.00.

Search for **IMP-IL001** and select its finding. Inspect the evidence snapshot and source pointers. In **Owner and notes**, assign yourself and add a note describing the fictional evidence review. Activity author is entered manually for this local demo.

In **Change status**:

1. Change **open → investigating**, with a reason, then select Save status.
2. Change **investigating → confirmed**, enter **20.00**, and provide the review reason.

Confirmation is a reviewer decision and can be less than the original potential amount. It cannot be zero, negative or greater than the potential amount.

## 5. Record a synthetic recovery

Expand **Record or reverse a recovery** and enter:

- Recovery amount: **10.00**.
- Recovery reference: **DEMO-REC-001**.
- Recovery note: **Synthetic partial recovery for portfolio testing**.

Select **Record recovery**. Expected for this case and the overall workflow if no other cases have been confirmed:

| Measure | Expected |
|---|---:|
| Confirmed amount | $20.00 |
| Net recorded recoveries | $10.00 |
| Confirmed outstanding | $10.00 |

Try a new recovery of **11.00** with reference DEMO-REC-002. It must be rejected because only $10 remains. Change the amount to **10.00** and record it. Net recoveries should become $20 and confirmed outstanding $0. Then change the case to **resolved**, with a reason.

These are demo ledger entries, not real money transfers or evidence of bank settlement. For actual business data, use references supported by the financial system.

## 6. Check persistence and corrections

- Run detection again: zero new findings; the case remains resolved.
- Refresh the browser or restart Streamlit: the saved case, events and ledger persist in PostgreSQL.
- To correct a recovery on a resolved case, reopen **resolved → confirmed** first. Select an active recovery, provide a reversal reason, and choose **Reverse selected recovery**. The whole selected receipt is reversed, retained in history, and can only be reversed once. Then record a corrected recovery with supporting reference/notes.
- Active recovery references cannot repeat within one case. A fully reversed reference can be used for the corrected entry.
- A confirmed case with a remaining balance can be closed only by explicitly checking **Close with an unrecovered balance** and giving a reason. The balance remains outstanding in the financial metrics; closure does not turn it into recovery.
- Withdrawing confirmation (**confirmed → investigating**) requires net recoveries to be zero. Original events remain visible.

## 7. Optional pgAdmin checks

```sql
SELECT version FROM schema_migrations ORDER BY version;
SELECT status, count(*) FROM findings
WHERE tenant_id='demo-distributor'
  AND rule_code='PRICE_UNDERBILLING' AND rule_version='1'
GROUP BY status;
SELECT event_type, actor, amount, created_at
FROM case_events
WHERE tenant_id='demo-distributor'
ORDER BY event_sequence DESC
LIMIT 20;
```

Expect migrations 001, 002 and 003. Avoid modifying audit rows directly; use corrective actions through the application.

## Current scope

The detector saves only the existing invoice-price underbilling rule. AI-generated explanations, external accounting integrations, verified identity, multi-user authorization and hosted tenant isolation remain future work. Author and owner names are labels in this local prototype. The evidence explanation is deterministic and traceable to source values.
