# Identity, company membership and authorization

Phase 8A (migration 004) added identities, memberships and optional case actor IDs.
Phase 8C enables the web login gate, service authorization and membership management.
Migration 005 adds append-only membership audit events. Existing case history is
not rewritten or retroactively attributed to verified accounts.

## Identity

Streamlit performs Google OpenID Connect authentication using private
`.streamlit/secrets.toml`. The web application consumes verified `iss`/`sub` claims,
checks the Google issuer and token expiry, and registers the identity with no
memberships. Email is display metadata, never an automatic account-linking or
company-access key. Disabled app accounts are never reactivated by sign-in.
No passwords or identity-provider tokens are stored in the database.

Issuer and subject identify an account; name/email changes do not create another
account. Signed identity claims and secrets must never be copied into application
logs or reports. Case JSON exports include the internal actor UUID, not OIDC
subject or tokens. Expired identities must sign out and sign in again, including
when a Streamlit identity cookie still exists.

Reference: https://docs.streamlit.io/develop/concepts/connections/authentication

## Company access

| Role | Permissions |
| --- | --- |
| viewer | Read dashboards, cases, reports and exports |
| analyst | Viewer permissions plus imports, detection and case changes |
| admin | Analyst permissions plus company membership and role management |

The company selector lists only active memberships for an active account. Roles
are per company. Changing user, company or role clears business session state,
including uploaded-file validation, receipts, selections and request keys. Only
the raw connection pool is cached globally; identities and scopes are not.

`CompanyEngine` attaches an immutable account/company/expiry context to each
connection and removes it before returning the connection to the pool. It is a
scope carrier, not a SQL sandbox. The dashboard, case and import entry points call
`require_access` in their database operation. Each call queries current account
and membership state. Write checks lock those rows for the transaction, so a
concurrent revocation waits for an already authorized write to finish. Subsequent
operations see the updated role. In-flight reads and downloaded files cannot be
recalled by a later membership change.

The dashboard performs its authorization check after setting the read-only
repeatable-read transaction mode, before querying business data. Scope mismatch,
expired identity, inactive account, inactive membership and insufficient role are
denied. Viewer write controls are hidden as well as rejected by services.

## Administration and history

New users sign in once and share their internal account UUID with an administrator.
Only company Admins can list or update that company's memberships in the web app.
Member changes serialize on a company-specific advisory lock and preserve at least
one effective active Admin. Unknown/inactive targets are rejected. Changes and
first-Admin bootstrap are recorded in append-only `membership_events`.

The first Admin is granted by `scripts/bootstrap_admin.py`, using trusted local
operator database access, an exact UUID, and a printed target review. It refuses
companies with an existing Admin membership. There is no public bootstrap route,
automatic email-domain grant, self-selected role, or automatic Admin on first login.

Authenticated case writes ignore supplied author text and use the current account
ID and display name. Detection records the initiating account and retains its rule
metadata. Idempotency fingerprints bind authenticated case actions to the internal
UUID. Legacy events keep null actor IDs and original labels. Assigned owner remains
a descriptive workflow label, not an authorization assignment.

## Boundary and production work

Raw SQLAlchemy engines used by local scripts/tests are trusted maintenance
interfaces. Service helpers explicitly preserve this mode for existing scripts;
all web business calls use `CompanyEngine`. Do not expose these raw-engine helpers
as HTTP APIs or give users direct database credentials. A future API must construct
an authenticated scope after verifying the caller, not accept user/tenant context
from a request without verification.

This is application-level authorization, not PostgreSQL row-level security.
Database owners can change accounts, bypass service policies or disable triggers.
Production work still includes restricted database privileges, RLS and its tests,
protected audit retention, session/identity operational policies, deployment/TLS,
secrets operations, load/concurrency testing and recovery procedures. No hosted
multi-company security certification is claimed.

## Validation

97 tests passed in the local strict runner: 63 unit/fixture and 34 integration
tests using the embedded PostgreSQL-compatible engine/socket adapter. Coverage
includes no implicit access, email non-linking, identity expiry, role restrictions,
cross-company denial, all case mutation entry points, real imports and detection,
verified actors, revocation, inactive accounts, scope cleanup, bootstrap, last-Admin
protection and audit persistence. The existing financial rules and workflows pass.

Streamlit AppTest with mocked Google identities passed the full application flow,
Admin membership changes, Viewer read-only reports, scope clearing, revocation and
anonymous denial. The migration runner was exercised twice in the UI harness.
Google sign-in/sign-out was independently verified by the user in the standalone
check on Windows. Native PostgreSQL 16/Python 3.13 CI for this update and real
Google login into the full workspace remain local/hosted follow-up checks.

Install and bootstrap instructions: [Phase 8C setup](../PHASE8C_SETUP.md).
