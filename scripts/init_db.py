from pathlib import Path
from marginguard.db import get_engine

engine = get_engine()
# psycopg executes the initial migration as one transaction. Existing schema fails safely.
with engine.connect() as conn:
    raw = conn.connection.driver_connection
    raw.execute(Path("sql/001_initial.sql").read_text(), prepare=False)
    raw.commit()
print("Applied migration 001.")
