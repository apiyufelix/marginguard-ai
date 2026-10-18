# MarginGuard AI — Portfolio Case Study

**Author:** Felix Apiyu  
**Focus:** Business analytics, data quality, financial reconciliation and operations workflow  
**Stack:** Python, Streamlit, PostgreSQL, SQLAlchemy, pandas and psycopg

## Problem and customer hypothesis

A distributor comparing order agreements with posted invoices needs a review process that establishes source reliability, explains the calculation, retains evidence, distinguishes authorized adjustments and tracks supported recoveries.

MarginGuard AI explores this problem for small B2B industrial or maintenance-supply distributors using ERP exports. The niche, need and willingness to pay require customer discovery and pilots.

## Solution

Related CSV uploads are checked for required fields, exact monetary values, identities and cross-file relationships before an atomic database import. The rule compares posted invoice quantities and prices with agreed net order prices.

Detection captures the evidence and saves only findings not already recorded for that rule version and invoice line. Reviewers can assign ownership, document evidence, confirm a supported amount or dismiss a case with a reason. Recovery entries can be corrected through reversals while retaining the original history.

The dashboard separates current source exposure from saved investigation balances. Case reports package the evidence, status and activity. Deterministic summaries explain calculations and suggest checks, with possible causes labelled as hypotheses.

## Design choices

| Choice | Reason |
|---|---|
| Modular Python services behind Streamlit | Test financial rules, validation and case policies independently of the UI. |
| PostgreSQL relationships and composite tenant keys | Enforce source relationships and prevent cross-tenant record links. |
| Decimal/NUMERIC and line-level rounding | Preserve financial precision and reproducibility. |
| Atomic imports and case actions | Avoid partial uploads or a case change without its event. |
| Idempotent detection and action identifiers | Prevent repeat scans or submissions from duplicating findings or recoveries. |
| Case versions and row locks | Reject stale edits and protect transactional consistency. |
| Append-only events and reversals | Preserve review and correction history. |
| Read-only dashboard snapshot | Keep related analytic reads consistent without changing case data. |

## Demonstrated results

The seed-42 fixture contains 40 fictional customers, 60 products, 500 orders and 500 invoices. Detection matches **116 candidate lines and $69,506.40 potential underbilling**. The additional valid sample adds two candidates and $70, giving 118 and $69,576.40.

These are synthetic results, not customer savings, confirmed business losses or recovered cash. Sample line IMP-IL001 has 10 units billed at $18 against an agreed $20, creating a $20 candidate amount. A reviewer still determines whether any amount is supported for confirmation.

The Phase 5 development harness passed **80 tests**, including unit/fixture and PostgreSQL integration checks using embedded PostgreSQL. Streamlit AppTest exercised uploads, detection, review actions, recovery corrections, report controls, filters and fresh-session persistence. The default local run skips 21 optional integration tests. See [verification details](phase5_verification.md) for the environment and limits.

## Skills demonstrated

The project translates a business control into a precise financial rule, relational model and operational workflow. It demonstrates related-source validation, SQL, exact financial calculations, transactional state changes, evidence retention, audit history, dashboard design, Python testing and technical documentation.

## Limits and next steps

This is a local development application. Phase 8 adds Google login, explicit company memberships, role checks and verified case actors. Assigned owners and legacy actor labels remain user-entered. Production database row security and hosted operations remain incomplete. The implemented rule covers invoice-price underbilling; freight policies, credits, rebates, foreign exchange and other leakage types need additional evidence and rules. Recorded recovery is not independently verified bank settlement.

Next, validate matching and approved-pricing assumptions with prospective users, then measure review time, supported confirmation rates and export availability in a controlled pilot. Commercial engineering would add restricted database permissions, row-level security, broader concurrency testing, hosted recovery operations and accounting integrations. See [current access design and verification](access_design.md).

## Suggested portfolio description

Built a Python, Streamlit and PostgreSQL application that validates related order/invoice CSVs, detects evidence-backed pricing discrepancies, and tracks investigation decisions and recovery corrections. Added reproducible synthetic data, exact financial calculations, append-only case activity, executive analytics and portable reports. Verified the workflow with 80 automated tests in the development harness; the original fictional benchmark identifies 116 candidate lines and $69,506.40 in potential underbilling.
