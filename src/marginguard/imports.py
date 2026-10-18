"""Append-only CSV bundle imports with tenant-scoped validation and lineage."""
from __future__ import annotations
import json
from uuid import uuid4
from sqlalchemy import text
from marginguard.validation import CONTRACTS, parse_bundle, validate_context

class MigrationRequired(RuntimeError):
    pass

class ImportRejected(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('Upload validation failed. No records were imported.')


def _context(conn, tenant):
    if not conn.execute(text("SELECT 1 FROM schema_migrations WHERE version='002'")).scalar():
        raise MigrationRequired('Apply migration 002 before uploading data.')
    if not conn.execute(text('SELECT 1 FROM tenants WHERE tenant_id=:tenant'), {'tenant':tenant}).scalar():
        raise ValueError('Configured organization does not exist.')
    # Names come exclusively from application-owned contracts, never user SQL.
    data = {}
    for name, fields in CONTRACTS.items():
        data[name] = [dict(x) for x in conn.execute(text(f'SELECT {", ".join(fields)} FROM {name} WHERE tenant_id=:tenant'), {'tenant':tenant}).mappings()]
    hashes = set(conn.execute(text('SELECT file_sha256 FROM import_batches WHERE tenant_id=:tenant'), {'tenant':tenant}).scalars())
    return data, hashes


def validate_upload(conn, tenant, uploads):
    report = parse_bundle(uploads, tenant)
    if report.ok:
        data, hashes = _context(conn, tenant)
        validate_context(report, data, hashes)
    return report


def commit_upload(engine, tenant, uploads):
    """Re-parse and revalidate under a per-tenant transaction lock at commit time."""
    with engine.begin() as conn:
        conn.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:tenant,0))'), {'tenant':tenant})
        report = validate_upload(conn, tenant, uploads)
        if not report.ok:
            raise ImportRejected(report)
        batches = {}
        for f in report.files:
            batch = str(uuid4())
            batches[f.dataset] = batch
            conn.execute(text('''INSERT INTO import_batches
                (tenant_id,batch_id,file_name,file_sha256,status,dataset,row_count,original_csv)
                VALUES(:tenant,:batch,:name,:sha,'staged',:dataset,:rows,:content)'''),
                {'tenant':tenant,'batch':batch,'name':f.file_name,'sha':f.sha256,'dataset':f.dataset,'rows':len(f.rows),'content':f.content})
            conn.execute(text('''INSERT INTO import_rows(tenant_id,batch_id,row_number,source_key,normalized_data)
                VALUES(:tenant,:batch,:row,:key,CAST(:data AS jsonb))'''),
                [{'tenant':tenant,'batch':batch,'row':row['_source_row'],
                  'key':row[next(iter(CONTRACTS[f.dataset]))],
                  'data':json.dumps({k:v for k,v in row.items() if k!='_source_row'}, default=str)} for row in f.rows])
            conn.execute(text("UPDATE import_batches SET status='validated' WHERE tenant_id=:tenant AND batch_id=:batch"), {'tenant':tenant,'batch':batch})
        # Dependency order is fixed even if the user selects files in a different order.
        for dataset, fields in CONTRACTS.items():
            f = next((x for x in report.files if x.dataset==dataset), None)
            if f is None:
                continue
            columns = ['tenant_id',*fields,'import_batch_id','source_row']
            params = [{'tenant_id':tenant,**{k:v for k,v in row.items() if k!='_source_row'},
                       'import_batch_id':batches[dataset],'source_row':row['_source_row']} for row in f.rows]
            conn.execute(text(f'INSERT INTO {dataset} ({", ".join(columns)}) VALUES ({", ".join(":"+x for x in columns)})'),params)
        for batch in batches.values():
            conn.execute(text("UPDATE import_batches SET status='committed' WHERE tenant_id=:tenant AND batch_id=:batch"), {'tenant':tenant,'batch':batch})
        receipt = [{'dataset':f.dataset,'rows':len(f.rows),'batch_id':batches[f.dataset]} for f in report.files]
    return receipt


def recent_imports(conn, tenant):
    return [dict(x) for x in conn.execute(text('''SELECT file_name,dataset,row_count,status,imported_at
        FROM import_batches WHERE tenant_id=:tenant ORDER BY imported_at DESC,batch_id LIMIT 20'''),{'tenant':tenant}).mappings()]
