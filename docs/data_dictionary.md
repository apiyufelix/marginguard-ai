# Data dictionary and synthetic fixture contract

Every business table uses `tenant_id`; composite keys preserve company-local IDs. Financial values are USD and timestamps are timezone-aware where applicable. Business document dates use DATE.

| Table | One row represents | Important fields |
|---|---|---|
| tenants | One organization | tenant_id, currency |
| customers | One customer account in an organization | customer_id, payment_terms_days |
| products | One SKU | product_id, standard_cost, list_price |
| orders | One sales order | order_id, customer_id, order_date, status |
| order_lines | One agreed product line | order_line_id, quantity, agreed_net_unit_price, unit_cost_snapshot |
| invoices | One invoice for one order | invoice_id, order_id, invoice_date, status |
| invoice_lines | One billed slice of an order line | invoice_line_id, order_line_id, quantity, invoiced_net_unit_price |
| freight_charges | One freight charge record | freight_id, order_id, carrier_cost, customer_charge, policy |
| credits | One credit against one invoice line | credit_id, amount, issued_on, reason |
| import_batches | One imported source file version | batch_id, file_sha256, status |
| findings | One rule-version result against one invoice line | finding_id, potential_loss, evidence JSON, status |
| case_events | One case action or recovery ledger entry | event_id, actor, event_type, amount, details JSON |

Actual schema, types, nullability, constraints and keys are authoritative in `sql/001_initial.sql`. Text keys make fictional data and external IDs readable. In a production import, retain external source IDs separately from stable internal keys where needed.

## Synthetic data design

Fictional industrial distributor: 40 customer accounts, 60 SKUs, 500 fulfilled orders, multiple product lines, varying quantities, agreed discounts, three freight policies and 50 documented partial-return credits. January–June 2026 orders, invoices within four days, August credits. Seed 42 produces identical files. Product categories are illustrative; these are not modeled industry distributions or a statistically representative market sample.

Invoice line scenarios: clean, 10% price underbilling, clean split billing, and a small set of overbilling examples. Scenario selection is random with weights 82/10/6/2, so observed counts will differ from exact percentages. Overbilling is deliberately excluded from the underbilling rule but could warrant a separate customer-protection review.

`ground_truth.csv`: invoice_line_id, scenario and expected_underbilling. Never load these labels into the analytics inputs. `manifest.json`: row counts, seed, expected flagged count and total exposure. These are test oracles for synthetic fixtures, not performance claims on real data.

Initial data is clean structurally. Later ingestion tests should add separate malformed fixtures: unknown SKU/customer keys, duplicate source IDs, negative amounts, missing prices, void invoices, revised contracts, over-invoiced cumulative quantities and ambiguous matches. Do not mix invalid fixtures into the happy-path seed.
