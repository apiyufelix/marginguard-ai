# MarginGuard AI

**An evidence-based invoice underbilling investigation application for B2B distributors.**

MarginGuard compares posted invoice prices with agreed order prices, preserves the evidence, and helps reviewers track decisions and recorded recoveries. It connects source validation, exact financial rules, case management and executive reporting in one local portfolio application.

**Stack:** Python · Streamlit · PostgreSQL · SQLAlchemy · pandas · psycopg

**Current scope:** local prototype with deterministic rule-based explanations and manually entered reviewer labels. Verified identity, hosted authorization and accounting reconciliation are future work.

## Business problem

Order and invoice exports can contain pricing differences that require review. A useful process must establish which records match, calculate the discrepancy consistently, retain the supporting evidence, and distinguish suspected exposure from confirmed amounts and recorded recovery.

The initial customer hypothesis is a small industrial or maintenance-supply distributor working from ERP exports. The niche and willingness to pay require customer discovery; no commercial demand or customer savings are claimed.

## Current capabilities

| Area | Behavior |
|---|---|
| Data onboarding | Related CSV uploads, strict headers, typed validation, relationship checks, duplicate-file handling and atomic imports. |
| Detection | Posted invoice-price underbilling, exact decimal calculations and idempotent saved findings. |
| Investigation | Captured evidence, source pointers, ownership, notes, confirmation, dismissal and controlled transitions. |
| Recovery ledger | Bounded entries, unique active references, reversals and append-only case activity. |
| Decision support | Evidence-based summaries, reconciliation issues and suggested checks with possible causes labelled as hypotheses. |
| Reports | Selected-case HTML/JSON and filtered investigation CSV exports. |
| Analytics | Customer/invoice-date filters, monthly exposure, customer/product concentrations, case progress, aging and review priorities. |

## Financial rule

For a posted invoice line:

```text
Potential underbilling = invoice quantity × max(agreed net unit price − billed net unit price, 0)
```

Net prices exclude tax. Amounts use half-up rounding to cents at invoice-line level. PostgreSQL uses NUMERIC and Python calculations use Decimal; float conversion is limited to chart/display data.

For synthetic sample line `IMP-IL001`, **10 × ($20 − $18) = $20** potential underbilling. Review determines the supported confirmation amount. Recovery entries record supported receipts and corrections; closure does not turn an outstanding balance into recovery.

## Reproducible synthetic benchmark

The included seed-42 fixture contains fictional customers, products, orders, invoices, freight records and credits. The implemented detector currently covers invoice-price underbilling.

| Dataset state | Candidate invoice lines | Potential underbilling |
|---|---:|---:|
| Original fixture: 40 customers, 60 products, 500 orders and 500 invoices | 116 | $69,506.40 |
| Original fixture plus the valid Phase 2 sample import | 118 | $69,576.40 |

These are synthetic benchmark amounts, not verified customer loss, revenue generated or money recovered. Fixture truth labels support validation and are not loaded into application tables.

## Run locally

For an existing configured project, run from its root:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For a fresh installation, follow [Windows setup](docs/setup_windows.md). It covers the environment, PostgreSQL role/database, connection settings, migrations and seed loading. Initialization is only for an empty database; an existing working installation should keep its current data.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The default run has **80 tests: 59 passing and 21 skipped integration tests**. Set `MARGINGUARD_TEST_DATABASE_URL` to a disposable PostgreSQL database to enable integration tests, which create and drop isolated schemas.

The latest complete development run passed all 80 tests using embedded PostgreSQL through its socket adapter. Streamlit AppTest also checked filters, empty selections, imports, detection, case actions, recoveries, corrections, report controls and fresh-session persistence. See [Phase 5 verification](docs/phase5_verification.md) for the environment and limits. Native Windows PostgreSQL/Python 3.13 verification is performed separately on the user's machine.

## Project layout

| Path | Purpose |
|---|---|
| `app.py` | Streamlit navigation and entry point. |
| `src/marginguard/` | Rules, validation, imports, cases, reports and dashboard services/UI. |
| `sql/` | Versioned PostgreSQL migrations 001–003. |
| `scripts/` | Initialization, migration, fixture generation and loading. |
| `data/synthetic/` | Fictional fixture and validation manifest. |
| `data/import_examples/` | Valid and invalid upload examples. |
| `tests/` | Unit, fixture and optional database checks. |
| `examples/` | Fixed synthetic HTML and JSON case reports. |
| `docs/` | Architecture, data dictionary, verification and portfolio guides. |

## Explore the project

- [Portfolio case study](docs/portfolio_case_study.md)
- [Demo walkthrough](docs/demo_walkthrough.md)
- [Windows setup](docs/setup_windows.md)
- [GitHub setup](docs/github_setup.md)
- [Data dictionary](docs/data_dictionary.md)
- [Case workflow architecture](docs/phase3_architecture.md)
- [Report architecture](docs/phase4_architecture.md)
- [Dashboard architecture](docs/phase5_architecture.md)

## Toward a commercial product

Validate export availability, approved-pricing rules and reviewer needs with prospective users. Engineering priorities include verified organization membership, role-based actions, restricted database permissions, tested tenant isolation, backup/restore procedures and accounting integrations. Freight and credit detectors require additional policy and transaction evidence. An optional model-based explanation provider can reuse the evidence boundary while financial calculations and decisions remain in the domain services.

Composite tenant keys and query predicates do not constitute a completed hosted authorization system. Git versions code and fictional fixtures; PostgreSQL contains live imports, cases and recovery history and needs separate backups.

## Project author

Felix Apiyu · Business Analytics and Fulfillment Operations
