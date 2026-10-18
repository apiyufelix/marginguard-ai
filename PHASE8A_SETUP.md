# Phase 8A — user and company-membership schema

Prerequisites: verified database backup/restore, branch `feature/auth-access`,
and the working application with migrations 001–003 applied.

1. Stop Streamlit with Ctrl+C in its terminal.
2. Extract the update ZIP into the existing project root. Accept replacement of
   `scripts/migrate_db.py`. The ZIP contains no `.env`, credentials, or data files.
3. Confirm your local `.env` still points to the working `marginguard` database.
   Do not paste its password or connection string into chat.
4. From the VS Code PowerShell terminal in the project root, run:

   ```powershell
   .\.venv\Scripts\python.exe scripts/migrate_db.py
   ```

   Expect 002 and 003 to be skipped and `Applied migration 004.`. The migration
   is additive. Do not run `init_db.py` or reseed data.

5. In pgAdmin, open Query Tool for `marginguard` and run:

   ```sql
   SELECT current_database(), version FROM schema_migrations ORDER BY version;
   SELECT count(*) AS users FROM app_users;
   SELECT count(*) AS memberships FROM tenant_memberships;
   ```

   Expect `marginguard`, versions 001–004, and zero users and memberships.
   Return the migration output before continuing to login integration.

This is a schema foundation only: login, authorization enforcement, account
provisioning, and membership management are not enabled by this update.
See `docs/access_design.md` for the intended roles and remaining work.

Validation: all 85 tests passed locally with the existing embedded
PostgreSQL-compatible engine, including five new access-schema integration tests.
Native PostgreSQL 16 verification remains available through GitHub Actions after
these files are committed and pushed. No UI code changed in this update.
