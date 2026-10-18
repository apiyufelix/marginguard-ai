-- Executed in one transaction by scripts/migrate_db.py. Existing demo records retain NULL lineage.
ALTER TABLE import_batches
 ADD COLUMN dataset text CHECK(dataset IN ('customers','products','orders','order_lines','invoices','invoice_lines')),
 ADD COLUMN row_count integer CHECK(row_count>0),
 ADD COLUMN original_csv bytea;
CREATE TABLE import_rows(
 tenant_id text NOT NULL,
 batch_id text NOT NULL,
 row_number integer NOT NULL CHECK(row_number>=2),
 source_key text NOT NULL,
 normalized_data jsonb NOT NULL,
 PRIMARY KEY(tenant_id,batch_id,row_number),
 FOREIGN KEY(tenant_id,batch_id) REFERENCES import_batches(tenant_id,batch_id)
);
DO $$
DECLARE dataset text;
BEGIN
 FOREACH dataset IN ARRAY ARRAY['customers','products','orders','order_lines','invoices','invoice_lines'] LOOP
  EXECUTE format('ALTER TABLE %I ADD COLUMN import_batch_id text, ADD COLUMN source_row integer', dataset);
  EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I CHECK ((import_batch_id IS NULL AND source_row IS NULL) OR (import_batch_id IS NOT NULL AND source_row IS NOT NULL))', dataset, dataset || '_lineage_pair');
  EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY(tenant_id,import_batch_id,source_row) REFERENCES import_rows(tenant_id,batch_id,row_number)', dataset, dataset || '_lineage_fk');
 END LOOP;
END $$;
INSERT INTO schema_migrations(version) VALUES('002');
