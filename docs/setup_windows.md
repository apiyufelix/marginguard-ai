# Windows development setup

Open the project folder in VS Code and run commands from its root. Package metadata requires Python 3.11+; SQL targets PostgreSQL 16+. Development verification used Python 3.12, while the user's working installation uses Python 3.13.

## Existing working installation

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

To run the checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The remaining initialization steps are for a fresh installation and empty database. Keep using existing data for a working installation.

## Fresh Python environment

Check the installed interpreter, then create the project environment:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

Select this `.venv` interpreter in VS Code. Calling its executable directly avoids PowerShell script activation.

For a new installation without an existing `.env`:

```powershell
Copy-Item .env.example .env
```

Keep an already configured `.env` rather than replacing its settings.

## Fresh PostgreSQL database

In pgAdmin, connect as your local administrator and open Query Tool against the existing `postgres` database. With auto-commit enabled, run these statements separately, replacing the password placeholder:

```sql
CREATE ROLE marginguard LOGIN PASSWORD 'YOUR_LOCAL_PASSWORD';
```

```sql
CREATE DATABASE marginguard OWNER marginguard;
```

Configure `.env` for that database:

```text
DATABASE_URL=postgresql+psycopg://marginguard:YOUR_URL_ENCODED_PASSWORD@localhost:5432/marginguard
DEMO_TENANT_ID=demo-distributor
```

URL-encode special password characters, such as `@` as `%40`, `#` as `%23` and `%` as `%25`. This owner role is for local development; hosted migration/application roles and authorization require separate design.

## Initialize, migrate and load the fixture

Only against the fresh empty application database:

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe scripts/migrate_db.py
.\.venv\Scripts\python.exe scripts/load_data.py
```

Initialization applies 001. The migration runner applies 002 and 003 and safely skips applied versions. The loader inserts the fixture atomically and refuses to overwrite an existing demo tenant. Ready-made CSVs are included; regenerating them is optional.

## Verify and launch

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The default run discovers 80 tests: 59 pass and 21 integration tests are skipped. Those optional tests use isolated schemas when `MARGINGUARD_TEST_DATABASE_URL` points to a disposable PostgreSQL database.

The initial Dashboard should show 116 candidate lines and $69,506.40 synthetic potential underbilling. In Investigations, Run detection saves the queue; repeated scans preserve decisions.

For the extra $70 sample, use Upload Data with all four CSVs in `data/import_examples/valid`, validate and import them once, then run detection. Source totals become 118 lines and $69,576.40. Use existing records when that sample was already imported.

## Common issues

| Message | Action |
|---|---|
| Requested Python version absent | Check `python --version` and use an installed supported interpreter. |
| PowerShell scripts disabled | Call `.\.venv\Scripts\python.exe` directly. |
| Project files missing | Open the actual project folder and run commands from its root. |
| Database unavailable | Check PostgreSQL is running and verify `.env` database, user and URL-encoded password. |
| Migration 003 required | Run `scripts/migrate_db.py` for the existing Phase 1/2 database. |
| Demo tenant already exists | Use its current data; the loader is preventing an overwrite. |

Dependencies use compatible ranges rather than a lockfile. After local verification, save an exact environment record with `.\.venv\Scripts\python.exe -m pip freeze > requirements-lock.txt`.
