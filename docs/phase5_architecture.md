# Phase 5 architecture

## Read model

`analytics.read_dashboard` reads the configured organization, current candidates, saved cases with their net recovery ledger, and order/customer identities. All reads occur in one PostgreSQL transaction set to `REPEATABLE READ, READ ONLY`. Every data query is scoped to the supplied tenant. This keeps the related reads on one committed snapshot and prevents this service from modifying business tables.

`analytics.make_snapshot` adds common invoice-date, customer and product dimensions while retaining saved evidence and financial values. Customer IDs and display names are resolved through the current order/customer records; saved invoice dates and product dimensions come from the case evidence snapshot. The application's existing import flow inserts source records without editing these relationships.

`analytics.dashboard_model` performs pure filtering, Decimal aggregation, grouping and ranking. `dashboard_page.render_dashboard` renders its results. `app.py` routes Dashboard to that component; uploads and investigations retain their existing services.

No schema migration, external API, additional dependency or write action is added. Dashboard data is reread on rerun and explicit refresh, rather than shared in a data cache.

## Metric definitions

| Metric | Basis |
|---|---|
| Potential underbilling | Current posted-invoice candidate amounts after the selected filters. |
| Invoice lines to investigate | Count of those current candidate rows. |
| Customers/products with candidates | Distinct captured IDs among those rows; matching names do not merge IDs. |
| Saved findings | Saved cases in the selected invoice cohort, including resolved and dismissed cases. |
| Confirmed amount | Current saved confirmation amounts in that cohort. |
| Net recorded recoveries | Recovery entries minus reversal entries for those cases. |
| Confirmed outstanding | Confirmation minus net recorded recovery, including resolved balances. |
| Net recovery / confirmed | Net recorded recoveries divided by confirmed amounts; absent when no amount is confirmed. |

Current source candidates and saved cases are separate populations. A resolved case may still have a current price discrepancy, while a saved case may remain after its source is no longer a current candidate. The dashboard never adds source potential to confirmation or reports dismissal as recovered money.

## Filter and chart semantics

Customer and inclusive invoice-date filters apply to both populations. Date filters select invoice cohorts, not case-creation dates or recovery-event dates. Financial case values are current balances for the selected cohort. The view is not an as-of historical ledger or a cash-receipts time series.

Missing invoice dates remain in all-time totals, are counted explicitly and are excluded from a selected date range. Monthly exposure includes only dated current candidates. Empty months between the first and last observed candidate month are filled with zero. Customer/product concentration shares use the entire selected source potential, even though the UI displays only the top 10.

Financial calculations and grouped totals use Decimal. Conversion to float occurs only when constructing display charts. Monetary tables use formatted exact values. Missing confirmation is not a financial decision to confirm zero; the aggregate simply contributes no confirmed amount, while selected-case pages retain their existing unconfirmed labels.

## Work review

Active statuses are open, investigating and confirmed. Age uses elapsed UTC calendar days since case creation, with explicit unknown-age handling. Future calendar dates and missing or invalid timestamps are not assigned an invented age. The 30-day indicator and age bands are operational review aids, not an SLA.

Priority rows rank by potential underbilling before confirmation and by outstanding confirmed amount after confirmation, then by older case age and finding ID. The amount basis is visible in each row. Resolved and dismissed cases are excluded. Fully recovered confirmed cases remain at zero for closure review. Ranking does not estimate confidence, root cause or probability of recovery.

Tenant predicates are query-scoping controls in the existing local application; this phase does not add verified organization membership or hosted tenant authorization.
