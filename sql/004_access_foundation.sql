-- Identity and membership foundation only. Application enforcement follows separately.
-- Applied by migrate_db.py inside its advisory-locked transaction.
CREATE TABLE app_users (
 user_id uuid PRIMARY KEY,
 oidc_issuer text NOT NULL CHECK(length(btrim(oidc_issuer))>0),
 oidc_subject text NOT NULL CHECK(length(btrim(oidc_subject))>0),
 display_name text NOT NULL CHECK(length(btrim(display_name))>0),
 email text,
 is_active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(oidc_issuer,oidc_subject)
);

CREATE TABLE tenant_memberships (
 tenant_id text NOT NULL REFERENCES tenants(tenant_id),
 user_id uuid NOT NULL REFERENCES app_users(user_id),
 role text NOT NULL CHECK(role IN ('viewer','analyst','admin')),
 is_active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,user_id)
);
CREATE INDEX tenant_memberships_user ON tenant_memberships(user_id,tenant_id);

-- Legacy actor labels remain intact. Later authenticated writes supply this ID.
-- Reference the membership so the actor belongs to the event's tenant.
ALTER TABLE case_events ADD COLUMN actor_user_id uuid;
ALTER TABLE case_events ADD CONSTRAINT case_events_actor_membership_fk
 FOREIGN KEY(tenant_id,actor_user_id)
 REFERENCES tenant_memberships(tenant_id,user_id);

INSERT INTO schema_migrations(version) VALUES('004');
