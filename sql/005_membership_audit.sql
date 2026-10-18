CREATE TABLE membership_events (
 event_id uuid PRIMARY KEY,
 tenant_id text NOT NULL REFERENCES tenants(tenant_id),
 actor_user_id uuid NOT NULL REFERENCES app_users(user_id),
 target_user_id uuid NOT NULL REFERENCES app_users(user_id),
 event_type text NOT NULL CHECK(event_type IN ('bootstrap','membership_set')),
 details jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX membership_events_tenant ON membership_events(tenant_id,created_at,event_id);
CREATE TRIGGER membership_events_append_only BEFORE UPDATE OR DELETE ON membership_events
 FOR EACH ROW EXECUTE FUNCTION prevent_case_event_changes();
INSERT INTO schema_migrations(version) VALUES('005');
