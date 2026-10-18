# Architecture and decisions

## Product boundary

Working niche: small US industrial/maintenance-supply distributors using exported order and invoice data. This is a product hypothesis to validate with interviews, not demonstrated commercial demand. First user: an operations or finance analyst reviewing suspected underbilling.

MVP workflow: import exports → validate keys and amounts → reconcile invoice lines against agreed order prices → calculate potential exposure → show evidence → investigate → confirm/dismiss → record recovery. Phase 1 supplies the schema, seeded database and read-only detection preview. Import UI, persistent detection jobs and case editing are later phases.

## Layers

Streamlit owns presentation. Python domain services own deterministic financial rules and future case transitions. SQLAlchemy handles parameterized database access. PostgreSQL owns relational integrity and durable records. The generator is a development tool, not a production ingestion route.

Retain this modular monolith while the portfolio grows. A future API and worker can reuse domain services; there is no need for microservices now. An optional language model may explain structured evidence; it must not invent losses or authorize recoveries.

## Relationships and grain

- Tenant → customers, products, imports and findings.
- Customer → orders → order lines.
- Order → invoices → invoice lines; invoice lines also reference an order line in the same order.
- Order → freight charges; invoice line → credits.
- Invoice line → findings → append-only case events.

Composite tenant keys and foreign keys prevent linking records across companies. They do not prevent a query from reading another company. There is no authenticated multi-tenant security in this local starter.

## Financial definitions

All demo records use USD. Prices are net of approved discounts and exclusive of sales tax. Unit prices and cost snapshots use NUMERIC(14,4), calculated money uses NUMERIC(14,2). Python uses Decimal and half-up rounding. Round once at invoice-line level.

Potential underbilling = invoice quantity × max(agreed net unit price − invoiced net unit price, 0), for posted invoices. Split invoice rows use their own quantities. This detects price differences, not unbilled remaining quantities. Positive margins are not proof that billing is correct.

Approved price changes not reflected in the order export may be false positives. Do not call them confirmed losses without review. Cancellations, tax, foreign exchange, rebates, credit offsets and unbilled shipments require additional rules. This starter does not compute total net profit or net all credits against findings.

Potential exposure, investigator-confirmed loss and actual recovery are different measures. Recovery and reversal events form a ledger; future services must enforce valid state transitions, actor authorization, recovery limits and append-only writes. The initial database has storage constraints, not the full workflow implementation.

Freight cost minus customer charge is not automatically leakage: free-shipping and fixed-fee policies are legitimate. Duplicate credit amounts are not enough to prove duplicate refunds. Returns authorization and external transaction references are needed before implementing that detector.

## Ingestion design for Phase 2

Land original uploads in private storage; calculate SHA-256; register an import batch. Parse a staging representation with row number, source identifiers and validation errors. Validate required columns, decimal precision, referential keys, date ordering, allowed statuses, currencies and cumulative billed quantity. Promote valid batches transactionally. Reject duplicate file hashes per tenant; define explicit source revision handling instead of silently overwriting.

Phase 1 seeds are trusted fixtures loaded directly and are not registered as imports. Add source batch/row lineage to each production transaction before real uploads; the current import_batches table reserves the batch lifecycle only.

## Toward SaaS

Before external users: authenticated identity and organization membership; roles; authorization; PostgreSQL row security; a restricted non-owner app role without BYPASSRLS; transaction-scoped tenant context; isolation tests; tenant-aware caches; TLS and secret management; backups and restore testing; private upload retention; audit-event permissions; migrations and CI. Tenant IDs must come from verified identity, never a dropdown or untrusted environment value in production.

Database owners and privileged roles can bypass row security in ordinary configurations. Merely adding tenant_id or filtering in the UI is insufficient. No SaaS readiness or security certification is claimed.

## Portfolio demonstration

Show a reproducible dataset, explain a seeded error with its invoice/order evidence, demonstrate clean split invoices, compare calculated exposure with hidden fixture truth, and distinguish suspected loss from recovered cash. Customer discovery should test data availability, false-positive tolerance and willingness to pay before expanding features.
