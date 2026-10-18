# Phase 8C — connect login and company roles

Prerequisites: backup/restore verified, migration 004 applied, Google sign-in and
sign-out working in `login_check.py`, local secrets saved and ignored by Git.
Continue on branch `feature/auth-access`.

## Install

Stop `login_check.py` with Ctrl+C in its running terminal to free port 8501.
Extract this ZIP into the existing project root, accepting file replacements.
The update does not contain `.env`, secrets, or customer data.

Keep `.env` connected to working `marginguard`, not the restore copy. Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/migrate_db.py
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address localhost --server.port 8501
```

Expect migration 005 applied; existing versions are skipped. Do not reinitialize
the database or rerun the seed loader. The migration adds an append-only
membership audit table and does not rewrite existing case history.

## First company administrator

Open `http://localhost:8501`. Sign in with your Google test account. The app now
creates a MarginGuard account, but does not automatically grant company access.
Expect a message saying no company membership has been granted. The sidebar shows
your **MarginGuard account ID** (a UUID), which is not a client secret or token.

Open a second PowerShell terminal in the same project. Replace the placeholder
with that exact UUID, keeping the quotation marks:

```powershell
.\.venv\Scripts\python.exe scripts/bootstrap_admin.py --tenant demo-distributor --user-id "PASTE_MARGIN_GUARD_ACCOUNT_UUID"
```

The command prints the database, company and account metadata so you can check
the target. Type `GRANT` only when these identify your own account in the intended
database/company. It creates the first Admin membership and records an audit
event. It refuses to run if any Admin membership already exists in that company.
This is a local maintenance command; the browser cannot invoke it.

Refresh the browser. Expect your company workspace and **Role: Admin**. Check
Dashboard, Investigations, Upload Data and Company access. Existing findings and
their original actor labels remain intact. New case events record your verified
account ID and name.

## Other users and role checks

In Google Cloud's testing configuration, add the other test account to Audience /
Test users. The person must sign in once to create their MarginGuard account and
share its UUID. As an Admin, open **Company access**, enter the exact account UUID,
choose Viewer/Analyst/Admin, and save. Reopen the page to refresh the member list.
Never grant access solely by matching an email address.

Viewer: Dashboard and read-only Investigations/reports. Analyst: those features
plus imports, detection and case actions. Admin: those features plus company
membership management. You cannot demote/deactivate the last active Admin through
the application. Deactivation retains history. Membership changes take effect on
the next database operation/page run; already downloaded data cannot be recalled.

## Validate and save progress

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
git check-ignore .streamlit/secrets.toml
git status --short
```

Without the opt-in disposable test database URL, 34 integration tests are skipped;
63 unit/fixture checks run. GitHub Actions' strict runner requires all 97 tests and
rejects skips. Its PostgreSQL 16 / Python 3.12 and 3.13 matrix runs on a pull request
to `main`, a push to `main`, or a manual workflow dispatch; pushing this feature
branch alone does not trigger the existing workflow.

Review your changes and stage the named update files only. Never stage secrets,
downloaded OAuth credential JSON, environment files or database backups. Commit
on `feature/auth-access`; keep this work local until the setup is verified.

See `docs/access_design.md` for the authorization boundary and validation limits.
