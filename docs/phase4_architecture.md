# Phase 4 architecture

## Scope and boundaries

The existing PostgreSQL case records remain authoritative. Phase 4 reads the selected case and its events through the existing case service, then produces explanations and exports without database writes. It introduces no migrations, additional dependencies or external API calls.

| Module | Responsibility |
|---|---|
| `reporting.py` | Pure explanation, reconciliation, report serialization and queue CSV functions. |
| `report_page.py` | Summary, suggested-check and report tabs for a selected case. |
| `cases_page.py` | Connects the report component to the existing investigation page and exports the current filtered queue. |

## Evidence and financial meaning

The explanation recalculates the existing invoice-price underbilling rule from captured quantity and net prices. A difference from the saved potential amount produces a data-quality issue; it does not replace that amount. Missing evidence and invalid financial ranges are also surfaced. When events are available, recoveries minus reversals are compared with the case service's net recorded recovery balance.

Potential underbilling, confirmed amounts, recorded recoveries and outstanding balances stay separate. A resolved case with a remaining balance still reports that balance as outstanding. An unconfirmed amount stays absent rather than becoming zero. Decimal values remain Decimal through calculations and are serialized as strings in JSON and exact numeric text in CSV.

Suggestions depend on the saved status and balance. Possible causes appear only as hypotheses for open or investigating cases. The method identifier is `rule_based_v1`; no model has inferred a verified cause or authorized a financial action.

## Export contracts

- **HTML:** a self-contained printable report with inline styling, escaped text, source evidence and case activity. It requires no network resources or scripts.
- **JSON:** report schema version `1`, UTC generation timestamp, organization identifier, case and rule versions, exact amounts, analysis, captured evidence and activity. Recovery reversals have a negative signed recovery effect and retain the original event link. Internal request tokens and fingerprints are excluded from event metadata.
- **CSV:** UTF-8 with BOM, fixed headers, explicit USD currency, and only the queue rows passed after the existing page filters. Formula-like text receives a leading apostrophe; actual Decimal amounts remain numeric text.

Both case downloads use the same render timestamp. Downloads do not rerun case actions. They represent the case version displayed on the page; a refresh is needed to include subsequent changes. Safe filenames use the invoice-line identifier with unsupported characters removed.

## Commercial evolution

These services provide a small, testable boundary for a future explanation provider. An eventual model should consume approved evidence and return reviewable suggestions while leaving monetary calculations and case decisions in the existing services. Authentication, authorization, hosted tenant isolation and accounting reconciliation require separate implementation before commercial deployment.
