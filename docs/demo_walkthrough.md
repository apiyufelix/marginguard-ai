# MarginGuard AI — Five-Minute Demo

**Presenter:** Felix Apiyu · [Hosted demo](https://marginguard-ai-demo.streamlit.app/)

Use synthetic data only. Sign in as Admin or Analyst for a live workflow; Viewers can inspect evidence and download reports. Prepare one case before recording. Prefer presenting its existing activity to repeatedly creating receipt entries. Reviewer onboarding is in [Reviewer access](reviewer_access.md).

## 1. Frame the business problem — 30 seconds

“MarginGuard helps a B2B distributor compare agreed order prices with posted invoice prices, investigate differences, and track review decisions and recorded recoveries. Every business record in this demonstration is fictional.”

Explain that potential underbilling needs investigation. The customer niche and willingness to pay remain hypotheses requiring discovery.

## 2. Find and save candidates — 45 seconds

Start Dashboard with All customers and the invoice-date filter cleared. The hosted base fixture has **116 candidate lines and $69,506.40 potential underbilling**. The local fixture plus the sample import has 118 and $69,576.40. State which dataset is on screen.

Show monthly exposure and one customer/product concentration. In Investigations, **Run detection** saves previously unseen candidates. A repeat scan should create zero new findings when the source data and rule version are unchanged; saved review decisions remain intact.

## 3. Trace one calculation — 60 seconds

Select a saved finding and explain its displayed quantity × max(agreed net price − billed net price, 0), with half-up rounding to cents. Use its actual numbers. IMP-IL001 is available only if the optional sample import was loaded; its example is 10 × ($20 − $18) = $20.

Show captured evidence, order/invoice identifiers and available source pointers. Seed records have no upload batch lineage; do not present missing upload pointers as an error. Show the rule-based explanation and a possible approved adjustment that would justify dismissal. Possible causes are hypotheses, not proven root causes.

## 4. Demonstrate the review workflow — 90 seconds

For a prepared case, show owner, notes, status and activity. Explain **open → investigating → confirmed → resolved**, with dismissal available when supported. Confirmation may be lower than the candidate amount.

For a live edit, choose an open fictional case and add a note beginning “DEMO ONLY —”. Move it to investigating with a reason, then confirm only the supported demonstration amount, within the displayed potential amount.

If demonstrating recovery, make one clearly fictional entry within the confirmed outstanding balance. Use a unique reference beginning DEMO- and a note saying “Fictional demonstration entry; no money received.” Never describe it as real cash recovered. For repeated presentations, show the existing entry instead of adding another. Reversals retain history; reopening a resolved case is required before correcting its recovery entries.

Show potential, confirmed, net recorded recovery and confirmed outstanding as separate measures. Resolve only with an appropriate reason; explicitly closing with an unrecovered balance does not count the balance as recovered. A Viewer presentation should show prepared history instead of mutation forms.

## 5. Export and explain access — 45 seconds

Download the selected-case HTML report and open it. Show evidence, explanation and case activity. JSON is the structured export; **Download filtered cases (CSV)** exports the visible investigation queue for Excel. Reports describe the case at generation time.

Briefly show the Viewer session with Dashboard and Investigations available and write/admin controls hidden. Each reviewer signs in using their own account and receives an explicit membership. Do not expose Company access tables containing other reviewers' personal details in a public recording.

## 6. Close with evidence and limits — 30 seconds

“The original fictional benchmark identifies 116 candidates totaling $69,506.40 in potential underbilling. The project has a 97-test suite and PostgreSQL CI across Python 3.12 and 3.13. The hosted demo combines data validation, exact calculations, investigation history, company roles and portable reporting. Customer validation and production operations are the next steps.”

The default local test command skips 34 integration checks unless a disposable database is configured. This is a portfolio demo, not a claim of customer savings, verified settlement or production certification.

## Screenshot capture guide

Capture real screens after hosted validation; no mock screenshots are included in this update.

| Suggested filename | Screen and purpose |
|---|---|
| dashboard.png | Overall fictional exposure and monthly/customer concentration. |
| case-evidence.png | One selected finding, exact calculation and source evidence. |
| case-activity.png | Prepared fictional review decisions and recovery history. |
| case-report.png | Exported HTML report with evidence and activity. |

Use consistent browser zoom and crop to the app content. Hide personal account IDs/emails, browser profile details and any secrets. Keep the fictional-data labels and metric names visible. Save approved images under docs/screenshots/ and add README image links only after the files exist. Do not publish membership tables with reviewer identities.
