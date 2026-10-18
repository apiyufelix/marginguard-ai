# MarginGuard AI — Phase 5: Executive Dashboard

This update expands Dashboard with customer and invoice-date filters, monthly source exposure, customer/product concentrations, case status, active-case aging and a ranked review list. Install it after your working Phase 4 application. No database migration or new package is required.

## 1. Install

Stop Streamlit with **Ctrl+C**. Extract `MarginGuard_AI_Phase5_Update.zip`, open the inner `MarginGuard_AI_Phase5_Update` folder, and copy all its contents into:

`C:\Users\apiyu\OneDrive\Lecture Notes\Application\MarginGuard AI`

Merge folders and replace matching files. The update replaces `app.py`, adds two dashboard modules, adds analytic tests, updates the existing database test file and supplies these notes. Keep using your existing database and virtual environment.

## 2. Check and launch

From your VS Code project terminal:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The default test command should report **80 tests**, with **59 passing** and **21 skipped**. The skipped tests require `MARGINGUARD_TEST_DATABASE_URL` for a disposable test database. The app does not require that setting.

## 3. Verify the overview

Open **Dashboard**. Leave **Dashboard customer** on **All customers** and **Filter by invoice date** unchecked.

| Source data currently loaded | Potential underbilling | Invoice lines to investigate |
|---|---:|---:|
| Original Phase 1 fixture | $69,506.40 | 116 |
| Fixture plus Phase 2 valid sample import | $69,576.40 | 118 |

These totals assume no additional source imports or manual source changes. Saved findings, confirmed amounts and recorded recoveries reflect your actual Phase 3 case activity. They may differ from an untouched demo database.

Case decisions do not rewrite source prices. Resolving or dismissing a case therefore does not remove its original source comparison from potential underbilling. Confirmed amounts and recoveries are displayed separately.

## 4. Explore the dashboard

| Tab | What it shows |
|---|---|
| Exposure analysis | Potential underbilling by invoice month, top 10 customers and products, and current candidate detail. |
| Case progress | Saved case statuses, active-case age, unassigned cases, recovery as a percentage of confirmation, and balances on resolved cases. |
| Review priorities | The 10 largest active case balances, with the amount basis, owner and case age. |

In **Exposure analysis**, hover over the monthly chart. Customer and product shares use all candidates in the current selection, even when only the top 10 are listed. IDs keep customers or products with the same display name distinct.

In **Case progress**, active means open, investigating or confirmed. Age is measured in UTC calendar days since the case was saved, rather than since the invoice date. A new case from an old invoice is still a new investigation. The age bands are review aids, not contractual SLAs.

In **Review priorities**, unconfirmed cases use potential underbilling; confirmed cases use confirmed outstanding. These are different amount bases and are labelled. Fully recovered confirmed cases remain available at a zero balance so they can be reviewed for closure. Resolved and dismissed cases are excluded from this active list.

## 5. Test the filters

1. Choose one customer. The source totals, saved-case balances, charts and review list should all narrow to that customer.
2. Check **Filter by invoice date** and select both dates. Both endpoints are inclusive.
3. Select a period with no invoices from this dataset. Totals should become zero and the page should explain the empty selection.
4. Clear the date checkbox and return to **All customers** to restore the full view.

The date range selects an **invoice cohort**. A January invoice's current recorded recovery is included when January is selected, even if the recovery was recorded in October. This dashboard does not show cash receipts by transaction date or reconstruct historical case balances.

Undated records stay in all-time totals and are excluded when a date filter is active. Undated candidates cannot appear in the monthly chart. Any such records are counted explicitly on the page.

## 6. Check that the existing workflow remains available

Return to **Investigations** and select a case. Its evidence, summary, report downloads and actions remain available. To investigate an item from the dashboard's review list, copy its invoice line and search for it in Investigations.

After saving a real review action or a synthetic demo action, return to **Dashboard** and choose **Refresh dashboard**. The saved-case balances should reflect the change. No dashboard interaction itself creates findings, confirmations or recoveries.

## Completion check

- All-customer source totals match the dataset you loaded.
- Customer and invoice-date filters affect the overview and all three tabs.
- Monthly and concentration views explain where potential underbilling sits.
- Saved case amounts match Investigations.
- Resolved balances remain outstanding when they have not been recovered.

The application remains a local portfolio prototype. Authentication, production authorization, hosted tenant isolation and accounting-system reconciliation are separate future work.
