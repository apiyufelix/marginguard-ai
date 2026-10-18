-- Apply once to an empty dedicated database. Never drop existing tables.
BEGIN;
CREATE TABLE schema_migrations(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE tenants(tenant_id text PRIMARY KEY, name text NOT NULL, currency char(3) NOT NULL CHECK(currency='USD'));
CREATE TABLE customers(
 tenant_id text NOT NULL REFERENCES tenants, customer_id text NOT NULL, name text NOT NULL,
 payment_terms_days integer NOT NULL CHECK(payment_terms_days>=0), PRIMARY KEY(tenant_id,customer_id));
CREATE TABLE products(
 tenant_id text NOT NULL REFERENCES tenants, product_id text NOT NULL, sku text NOT NULL, category text NOT NULL,
 standard_cost numeric(14,4) NOT NULL CHECK(standard_cost>=0), list_price numeric(14,4) NOT NULL CHECK(list_price>=0),
 PRIMARY KEY(tenant_id,product_id), UNIQUE(tenant_id,sku));
CREATE TABLE orders(
 tenant_id text NOT NULL REFERENCES tenants, order_id text NOT NULL, customer_id text NOT NULL,
 order_date date NOT NULL, status text NOT NULL CHECK(status IN ('fulfilled','partial','cancelled')),
 PRIMARY KEY(tenant_id,order_id), FOREIGN KEY(tenant_id,customer_id) REFERENCES customers(tenant_id,customer_id));
CREATE TABLE order_lines(
 tenant_id text NOT NULL, order_line_id text NOT NULL, order_id text NOT NULL, product_id text NOT NULL,
 quantity integer NOT NULL CHECK(quantity>0), agreed_net_unit_price numeric(14,4) NOT NULL CHECK(agreed_net_unit_price>=0),
 unit_cost_snapshot numeric(14,4) NOT NULL CHECK(unit_cost_snapshot>=0),
 PRIMARY KEY(tenant_id,order_line_id), UNIQUE(tenant_id,order_line_id,order_id),
 FOREIGN KEY(tenant_id,order_id) REFERENCES orders(tenant_id,order_id),
 FOREIGN KEY(tenant_id,product_id) REFERENCES products(tenant_id,product_id));
CREATE TABLE invoices(
 tenant_id text NOT NULL, invoice_id text NOT NULL, order_id text NOT NULL, invoice_date date NOT NULL,
 status text NOT NULL CHECK(status IN ('posted','void')),
 PRIMARY KEY(tenant_id,invoice_id), UNIQUE(tenant_id,invoice_id,order_id),
 FOREIGN KEY(tenant_id,order_id) REFERENCES orders(tenant_id,order_id));
CREATE TABLE invoice_lines(
 tenant_id text NOT NULL, invoice_line_id text NOT NULL, invoice_id text NOT NULL, order_id text NOT NULL, order_line_id text NOT NULL,
 quantity integer NOT NULL CHECK(quantity>0), invoiced_net_unit_price numeric(14,4) NOT NULL CHECK(invoiced_net_unit_price>=0),
 PRIMARY KEY(tenant_id,invoice_line_id),
 FOREIGN KEY(tenant_id,invoice_id,order_id) REFERENCES invoices(tenant_id,invoice_id,order_id),
 FOREIGN KEY(tenant_id,order_line_id,order_id) REFERENCES order_lines(tenant_id,order_line_id,order_id));
CREATE TABLE freight_charges(
 tenant_id text NOT NULL, freight_id text NOT NULL, order_id text NOT NULL, carrier text NOT NULL,
 carrier_cost numeric(14,2) NOT NULL CHECK(carrier_cost>=0), customer_charge numeric(14,2) NOT NULL CHECK(customer_charge>=0),
 policy text NOT NULL CHECK(policy IN ('pass_through','free_shipping','fixed_fee')),
 PRIMARY KEY(tenant_id,freight_id), FOREIGN KEY(tenant_id,order_id) REFERENCES orders(tenant_id,order_id));
CREATE TABLE credits(
 tenant_id text NOT NULL, credit_id text NOT NULL, invoice_line_id text NOT NULL, issued_on date NOT NULL,
 amount numeric(14,2) NOT NULL CHECK(amount>0), reason text NOT NULL,
 PRIMARY KEY(tenant_id,credit_id), FOREIGN KEY(tenant_id,invoice_line_id) REFERENCES invoice_lines(tenant_id,invoice_line_id));
CREATE TABLE import_batches(
 tenant_id text NOT NULL REFERENCES tenants, batch_id text NOT NULL, file_name text NOT NULL, file_sha256 char(64) NOT NULL,
 status text NOT NULL CHECK(status IN ('staged','validated','committed','rejected')),
 imported_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,batch_id), UNIQUE(tenant_id,file_sha256));
CREATE TABLE findings(
 tenant_id text NOT NULL REFERENCES tenants, finding_id text NOT NULL, invoice_line_id text NOT NULL,
 rule_code text NOT NULL, rule_version text NOT NULL, potential_loss numeric(14,2) NOT NULL CHECK(potential_loss>=0),
 status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','investigating','confirmed','dismissed','resolved')),
 assigned_to text, evidence jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,finding_id), UNIQUE(tenant_id,rule_code,rule_version,invoice_line_id),
 FOREIGN KEY(tenant_id,invoice_line_id) REFERENCES invoice_lines(tenant_id,invoice_line_id));
CREATE TABLE case_events(
 tenant_id text NOT NULL, event_id text NOT NULL, finding_id text NOT NULL,
 event_type text NOT NULL CHECK(event_type IN ('note','status_change','recovery','recovery_reversal')),
 actor text NOT NULL, details jsonb NOT NULL, amount numeric(14,2), created_at timestamptz NOT NULL DEFAULT now(),
 CHECK((event_type IN ('recovery','recovery_reversal') AND amount>0) OR (event_type NOT IN ('recovery','recovery_reversal') AND amount IS NULL)),
 PRIMARY KEY(tenant_id,event_id), FOREIGN KEY(tenant_id,finding_id) REFERENCES findings(tenant_id,finding_id));
CREATE INDEX orders_customer_date ON orders(tenant_id,customer_id,order_date);
CREATE INDEX invoice_lines_order_line ON invoice_lines(tenant_id,order_line_id);
CREATE INDEX findings_work_queue ON findings(tenant_id,status,created_at);
CREATE VIEW underbilling_candidates AS
SELECT il.tenant_id, il.invoice_line_id, il.invoice_id, il.order_line_id,
 il.quantity, ol.agreed_net_unit_price, il.invoiced_net_unit_price,
 round(il.quantity * (ol.agreed_net_unit_price-il.invoiced_net_unit_price),2) AS potential_loss
FROM invoice_lines il
JOIN order_lines ol USING(tenant_id,order_line_id,order_id)
JOIN invoices i USING(tenant_id,invoice_id,order_id)
WHERE i.status='posted' AND ol.agreed_net_unit_price>il.invoiced_net_unit_price;
INSERT INTO schema_migrations(version) VALUES('001');
COMMIT;
