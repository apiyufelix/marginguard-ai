"""Apply pending additive migrations after Phase 1. Safe to rerun."""
from pathlib import Path
from sqlalchemy import text
from marginguard.db import get_engine

root = Path(__file__).resolve().parents[1]
messages = []
with get_engine().begin() as conn:
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('marginguard-migrations',0))"))
    versions = set(conn.execute(text('SELECT version FROM schema_migrations')).scalars())
    if '001' not in versions:
        raise RuntimeError('Phase 1 schema is required. Use init_db.py only on an empty database.')
    for version, filename in [('002','002_import_lineage.sql'),('003','003_investigations.sql'),('004','004_access_foundation.sql'),('005','005_membership_audit.sql')]:
        if version in versions:
            messages.append(f'Migration {version} already applied; no changes needed.')
        else:
            conn.connection.driver_connection.execute((root/'sql'/filename).read_text(),prepare=False)
            messages.append(f'Applied migration {version}.')
for message in messages:
    print(message)
