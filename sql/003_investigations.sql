-- Additive migration, executed inside the versioned runner transaction.
ALTER TABLE findings
 ALTER COLUMN potential_loss TYPE numeric(24,2),
 ADD COLUMN confirmed_amount numeric(24,2),
 ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK(version>0),
 ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE findings ADD CONSTRAINT findings_confirmation_check CHECK(
 (status IN ('confirmed','resolved') AND confirmed_amount IS NOT NULL AND confirmed_amount>0 AND confirmed_amount<=potential_loss)
 OR (status NOT IN ('confirmed','resolved') AND confirmed_amount IS NULL)
);
ALTER TABLE case_events
 ALTER COLUMN amount TYPE numeric(24,2),
 ADD COLUMN request_key text,
 ADD COLUMN reverses_event_id text,
 ADD COLUMN event_sequence bigint GENERATED ALWAYS AS IDENTITY;
ALTER TABLE case_events DROP CONSTRAINT case_events_event_type_check;
ALTER TABLE case_events ADD CONSTRAINT case_events_event_type_check CHECK(
 event_type IN ('created','assignment','note','status_change','recovery','recovery_reversal')
);
-- Explicit IS NOT NULL closes the NULL loophole in the Phase 1 amount check.
ALTER TABLE case_events DROP CONSTRAINT case_events_check;
ALTER TABLE case_events ADD CONSTRAINT case_events_amount_check CHECK(
 (event_type IN ('recovery','recovery_reversal') AND amount IS NOT NULL AND amount>0)
 OR (event_type NOT IN ('recovery','recovery_reversal') AND amount IS NULL)
);
ALTER TABLE case_events ADD CONSTRAINT case_events_request_key_unique UNIQUE(tenant_id,request_key);
ALTER TABLE case_events ADD CONSTRAINT case_events_case_event_unique UNIQUE(tenant_id,finding_id,event_id);
ALTER TABLE case_events ADD CONSTRAINT case_events_reversal_fk
 FOREIGN KEY(tenant_id,finding_id,reverses_event_id) REFERENCES case_events(tenant_id,finding_id,event_id);
ALTER TABLE case_events ADD CONSTRAINT case_events_reversal_check CHECK(
 (event_type='recovery_reversal' AND reverses_event_id IS NOT NULL)
 OR (event_type<>'recovery_reversal' AND reverses_event_id IS NULL)
);
CREATE UNIQUE INDEX case_events_one_reversal ON case_events(tenant_id,reverses_event_id) WHERE event_type='recovery_reversal';
CREATE INDEX case_events_timeline ON case_events(tenant_id,finding_id,event_sequence);
CREATE FUNCTION prevent_case_event_changes() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Case events are append-only; record a corrective event instead.';
END $$;
CREATE TRIGGER case_events_append_only BEFORE UPDATE OR DELETE ON case_events
 FOR EACH ROW EXECUTE FUNCTION prevent_case_event_changes();
-- Keep the original column order/types and append evidence fields.
CREATE OR REPLACE VIEW underbilling_candidates AS
SELECT il.tenant_id,il.invoice_line_id,il.invoice_id,il.order_line_id,
 il.quantity,ol.agreed_net_unit_price,il.invoiced_net_unit_price,
 round(il.quantity*(ol.agreed_net_unit_price-il.invoiced_net_unit_price),2) AS potential_loss,
 ol.order_id,ol.product_id,
 ol.import_batch_id AS order_source_batch,ol.source_row AS order_source_row,
 il.import_batch_id AS invoice_source_batch,il.source_row AS invoice_source_row,
 i.invoice_date,o.order_date,c.name AS customer_name,p.sku
FROM invoice_lines il
JOIN order_lines ol ON ol.tenant_id=il.tenant_id AND ol.order_line_id=il.order_line_id AND ol.order_id=il.order_id
JOIN invoices i ON i.tenant_id=il.tenant_id AND i.invoice_id=il.invoice_id AND i.order_id=il.order_id
JOIN orders o ON o.tenant_id=ol.tenant_id AND o.order_id=ol.order_id
JOIN customers c ON c.tenant_id=o.tenant_id AND c.customer_id=o.customer_id
JOIN products p ON p.tenant_id=ol.tenant_id AND p.product_id=ol.product_id
WHERE i.status='posted' AND ol.agreed_net_unit_price>il.invoiced_net_unit_price;
INSERT INTO schema_migrations(version) VALUES('003');
