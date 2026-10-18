# MarginGuard AI — Four-Minute Demo

Use the working fictional dataset and existing saved cases. This walkthrough can be presented without recording new receipts or repeating an import. Start Dashboard on All customers with the invoice-date checkbox cleared.

## 1. Explain the problem — 30 seconds

"MarginGuard helps a distributor compare agreed order prices with posted invoice prices, then organize the evidence, review decisions and recorded recoveries. This demo uses fictional data. Potential underbilling needs investigation."

Show the source metrics: 116 candidate lines and $69,506.40 for the original fixture, or 118 and $69,576.40 after the valid sample import. Describe these as synthetic exposure, not savings.

## 2. Locate the exposure — 45 seconds

In Exposure analysis, show invoice-month exposure and one customer/product concentration. Select a customer and explain why IDs distinguish records with matching names. Clear the selection afterward.

If showing date filters, explain that they select invoice cohorts. The saved case amounts are current balances, rather than receipts occurring during that selected period.

## 3. Trace a case to evidence — 60 seconds

In Investigations, search IMP-IL001 if the valid sample is present. Its calculation is 10 × ($20 − $18) = $20. Otherwise select a saved finding and use its displayed quantity and prices.

Show captured evidence and source batch/row pointers where present. Initial seed records predate upload lineage and use order/invoice identifiers to locate source records. Show the rule-based summary and explain why an approved pricing adjustment could justify dismissal.

If useful, run detection again: after current candidates are saved it creates zero new findings and preserves the saved decisions.

## 4. Explain the workflow — 45 seconds

Show the current owner, status and activity timeline. Explain open → investigating → confirmed or dismissed. Confirmation can be lower than the potential amount.

For a case with recovery history, show confirmation, net recovery and outstanding side by side. Reversing a receipt retains its original event. Resolving a case with an unpaid balance leaves that amount outstanding. Present existing entries instead of repeatedly creating demonstration receipts.

## 5. Export the result — 30 seconds

In Reports, download the case HTML and show its evidence, summary and activity. JSON is the structured export; the investigation CSV opens in Excel. Set the desired queue filters in Investigations before downloading that CSV.

## 6. Close with verification — 30 seconds

"The original fixture matches 116 findings and $69,506.40, and the latest development harness passed 80 automated tests. The prototype demonstrates data quality, exact rules, transactional case handling and reporting. Customer validation, verified access and accounting integration are the next steps toward a commercial service."

For a deeper review, use the case study, data dictionary and architecture links in the README. The development database checks used embedded PostgreSQL; a default local run skips integration tests unless a disposable database is configured.
