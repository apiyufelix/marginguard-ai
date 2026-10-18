# MarginGuard AI — Phase 4: Decision Support and Case Reports

This update adds evidence-based summaries, suggested investigation checks, and portable reports to your working Phase 3 application. The explanations use local rules. No AI API key, new package or database migration is required.

## 1. Install the update

Stop Streamlit with **Ctrl+C** in its terminal. Extract `MarginGuard_AI_Phase4_Update.zip`, open the inner `MarginGuard_AI_Phase4_Update` folder, and copy all its contents into your existing project:

`C:\Users\apiyu\OneDrive\Lecture Notes\Application\MarginGuard AI`

Merge matching folders and replace matching files. Copy the contents into the project root, rather than leaving the update in a separate nested folder. This update includes the earlier dollar-sign evidence display fix.

Your Phase 3 application and migration 003 must already be installed. Keep using the existing database and environment; do not rerun the database initialization or seed scripts.

## 2. Run checks and launch

Run these commands in the VS Code terminal opened at your project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The default test run should discover **62 tests**, with **45 passing** and **17 skipped**. Database integration tests are skipped unless `MARGINGUARD_TEST_DATABASE_URL` points to a disposable test database. You do not need to configure it to use the app.

## 3. Inspect a case summary

Open **Investigations**. Search for **IMP-IL001** and select its finding. This line is available after importing the Phase 2 valid example and running detection. You can also select any other saved finding.

The new **Case summary and next checks** section contains three tabs:

| Tab | What to inspect |
|---|---|
| Summary | Captured pricing, saved potential amount, current review status, recorded recovery balance and source lineage. |
| Suggested checks | Investigation steps matched to the case status, with possible explanations clearly labelled as hypotheses for open cases. |
| Reports | HTML and JSON downloads for the selected case. |

For IMP-IL001, the price comparison is **10 × ($20 − $18) = $20** potential underbilling. Confirmation, recoveries and outstanding amounts must match your current saved case. If you recorded a $20 confirmation and one $10 recovery in Phase 3, the report should show $20 confirmed, $10 recovered and $10 outstanding. If you completed both recoveries, outstanding should be $0.

These summaries explain the evidence; they do not establish a root cause or make a confirmation decision. Missing evidence or a disagreement between the saved amount and the captured calculation is surfaced for review.

## 4. Download the selected case

In **Reports**:

1. Select **Download case report (HTML)**. Open the downloaded file in your browser. It includes the monetary totals, suggested checks, evidence and case activity. Use the browser's Print command to print or save as PDF.
2. Select **Download case data (JSON)**. This is the structured version, with exact decimal monetary values represented as strings, a report schema version and a UTC generation timestamp.

The downloads capture the case version currently displayed. Refresh the page to include changes made after it was rendered. Generating a report does not change the case or create a recovery.

The `examples` folder also contains `sample_case_report.html` and `sample_case_report.json`. These are fixed synthetic examples showing $20 confirmed, $10 recovered and $10 outstanding; they are not exports of your current database.

## 5. Export the filtered investigation queue

Apply the status filter or search in Investigations. Select **Download filtered cases (CSV)** beneath the queue. The CSV contains only the cases matching those filters, with case identifiers, customer/SKU, status, owner, exact USD amounts, case version and export timestamp.

An unconfirmed amount is blank rather than zero. Formula-like text is escaped for spreadsheet use. The HTML and JSON case reports remain available for the case's complete evidence and history.

## Completion check

- The existing dashboard, uploads and case actions still work.
- A selected case displays its summary and suggested checks.
- HTML and JSON reports match the selected case's displayed version and monetary totals.
- The queue CSV matches the current filters.

This phase adds local, rule-based decision support. External AI explanations, verified user identity, production tenant authorization and accounting-system connections remain future work.
