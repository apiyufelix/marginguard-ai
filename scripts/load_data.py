"""Atomic seed import, insert-only: refuse a non-empty demo tenant."""
import csv
from pathlib import Path
from sqlalchemy import MetaData, select
from marginguard.db import get_engine

engine=get_engine()
meta=MetaData(); meta.reflect(bind=engine)
order=['tenants','customers','products','orders','order_lines','invoices','invoice_lines','freight_charges','credits']
with engine.begin() as conn:
    if conn.execute(select(meta.tables['tenants']).where(meta.tables['tenants'].c.tenant_id=='demo-distributor')).first():
        raise RuntimeError('Demo tenant already exists; no data changed.')
    for name in order:
        with Path(f'data/synthetic/{name}.csv').open(newline='') as f:
            rows=list(csv.DictReader(f))
        conn.execute(meta.tables[name].insert(),rows)
print('Synthetic dataset loaded atomically.')
