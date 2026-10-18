"""CSV contracts and cross-file reconciliation. No database or UI dependencies."""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath

from marginguard.rules import underbilling

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000
# First column is the document key. Tenant identity is supplied by the app.
CONTRACTS = {
    'customers': {'customer_id': 'id', 'name': 'text', 'payment_terms_days': 'nonnegative_int'},
    'products': {'product_id': 'id', 'sku': 'id', 'category': 'text', 'standard_cost': 'price', 'list_price': 'price'},
    'orders': {'order_id': 'id', 'customer_id': 'id', 'order_date': 'date', 'status': ('fulfilled', 'partial', 'cancelled')},
    'order_lines': {'order_line_id': 'id', 'order_id': 'id', 'product_id': 'id', 'quantity': 'positive_int', 'agreed_net_unit_price': 'price', 'unit_cost_snapshot': 'price'},
    'invoices': {'invoice_id': 'id', 'order_id': 'id', 'invoice_date': 'date', 'status': ('posted', 'void')},
    'invoice_lines': {'invoice_line_id': 'id', 'invoice_id': 'id', 'order_id': 'id', 'order_line_id': 'id', 'quantity': 'positive_int', 'invoiced_net_unit_price': 'price'},
}

@dataclass
class Issue:
    file_name: str
    row: int | None
    column: str
    code: str
    message: str

@dataclass
class ParsedFile:
    dataset: str
    file_name: str
    sha256: str
    content: bytes
    rows: list[dict]

@dataclass
class Report:
    files: list[ParsedFile] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    preview: list[dict] = field(default_factory=list)

    @property
    def ok(self):
        return bool(self.files) and not self.issues

    def error(self, file_name, row, column, code, message):
        self.issues.append(Issue(file_name, row, column, code, message))


def _value(raw, kind):
    value = raw.strip()
    if not value:
        raise ValueError('A required value is missing.')
    if any(c in value for c in ('\x00', '\r', '\n')):
        raise ValueError('Control characters and multiline cells are unsupported.')
    if isinstance(kind, tuple):
        if value not in kind:
            raise ValueError('Allowed values: ' + ', '.join(kind) + '.')
        return value
    if kind in ('id', 'text'):
        if len(value) > (64 if kind == 'id' else 200):
            raise ValueError('Value is too long (ID: 64, text: 200 characters).')
        return value
    if kind in ('positive_int', 'nonnegative_int'):
        if not re.fullmatch(r'[0-9]+', value) or len(value) > 10:
            raise ValueError('Use a whole number without separators.')
        result = int(value)
        minimum = 1 if kind == 'positive_int' else 0
        if not minimum <= result <= 2_147_483_647:
            raise ValueError(f'Use an integer from {minimum} to 2147483647.')
        return result
    if kind == 'price':
        if not re.fullmatch(r'[0-9]{1,10}(\.[0-9]{1,4})?', value):
            raise ValueError('Use a nonnegative price with at most 10 integer and 4 decimal digits; no currency symbols or separators.')
        return Decimal(value)
    if kind == 'date':
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
            raise ValueError('Use an ISO date: YYYY-MM-DD.')
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError('Date does not exist.') from None
    raise ValueError('Unsupported field type.')


def parse_bundle(uploads: list[tuple[str, bytes]], tenant: str) -> Report:
    report = Report()
    if not uploads:
        report.error('', None, '', 'empty_bundle', 'Choose at least one CSV file.')
        return report
    if len(uploads) > len(CONTRACTS):
        report.error('', None, '', 'file_limit', 'Upload at most six files, one per dataset.')
        return report
    seen = set()
    for name, content in uploads:
        name = PurePosixPath(name.replace('\\', '/')).name
        dataset = PurePosixPath(name).stem.lower()
        if PurePosixPath(name).suffix.lower() != '.csv' or dataset not in CONTRACTS:
            report.error(name, None, '', 'filename', 'Use one of: ' + ', '.join(x+'.csv' for x in CONTRACTS) + '.')
            continue
        if dataset in seen:
            report.error(name, None, '', 'duplicate_dataset', 'Only one file per dataset is allowed in an upload.')
            continue
        seen.add(dataset)
        if len(content) > MAX_BYTES:
            report.error(name, None, '', 'size', 'File exceeds the 5 MiB application limit.')
            continue
        try:
            decoded = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            report.error(name, None, '', 'encoding', 'Save the file as UTF-8 CSV.')
            continue
        f = ParsedFile(dataset, name, hashlib.sha256(content).hexdigest(), content, [])
        report.files.append(f)
        reader = csv.reader(io.StringIO(decoded, newline=''), strict=True)
        try:
            header = next(reader, [])
            header = [x.strip() for x in header]
            required = set(CONTRACTS[dataset])
            if not header or len(header) != len(set(header)):
                report.error(name, 1, '', 'header', 'A nonempty header with unique column names is required.')
                continue
            missing = required - set(header)
            extra = set(header) - required - {'tenant_id'}
            if missing or extra:
                report.error(name, 1, '', 'columns', f'Missing columns: {", ".join(sorted(missing)) or "none"}. Unexpected columns: {", ".join(sorted(extra)) or "none"}.')
                continue
            keys = set()
            key_column = next(iter(CONTRACTS[dataset]))
            records = 0
            for row_number, cells in enumerate(reader, 2):
                if not cells:  # ignore physically blank CSV records
                    continue
                records += 1
                if records > MAX_ROWS:
                    report.error(name, row_number, '', 'row_limit', 'File exceeds 10,000 records.')
                    break
                if len(cells) != len(header):
                    report.error(name, row_number, '', 'row_shape', 'Cell count does not match the header.')
                    continue
                raw = dict(zip(header, cells))
                if 'tenant_id' in raw and raw['tenant_id'].strip() != tenant:
                    report.error(name, row_number, 'tenant_id', 'tenant_mismatch', 'The file belongs to another organization or has a blank tenant ID.')
                normalized = {'_source_row': row_number}
                for column, kind in CONTRACTS[dataset].items():
                    try:
                        normalized[column] = _value(raw[column], kind)
                    except ValueError as e:
                        report.error(name, row_number, column, 'value', str(e))
                if key_column in normalized:
                    if normalized[key_column] in keys:
                        report.error(name, row_number, key_column, 'duplicate_key', 'Document ID is repeated within this file.')
                    keys.add(normalized[key_column])
                if len(normalized) == len(CONTRACTS[dataset])+1:
                    f.rows.append(normalized)
            if records == 0:
                report.error(name, None, '', 'empty_file', 'File has no data records.')
        except csv.Error:
            report.error(name, None, '', 'csv_parse', 'CSV syntax is invalid or a cell is too large. Check quotes and delimiters.')
    return report


def validate_context(report: Report, existing: dict[str, list[dict]], existing_hashes: set[str]) -> Report:
    """Append database-aware issues using tenant-scoped context; call once per parse."""
    if not report.ok:
        return report
    combined = {name: {row[next(iter(contract))]: row for row in existing.get(name, [])}
                for name, contract in CONTRACTS.items()}
    for f in report.files:
        if f.sha256 in existing_hashes:
            report.error(f.file_name, None, '', 'duplicate_file', 'This exact file was already imported for this organization.')
        key = next(iter(CONTRACTS[f.dataset]))
        for row in f.rows:
            if row[key] in combined[f.dataset]:
                report.error(f.file_name, row['_source_row'], key, 'existing_key', 'Document ID already exists. This importer only appends new records.')
            else:
                combined[f.dataset][row[key]] = row
    skus = {x['sku'] for x in existing.get('products', [])}
    for f in report.files:
        for row in f.rows:
            def err(column, code, message):
                report.error(f.file_name, row['_source_row'], column, code, message)
            if f.dataset == 'customers':
                continue
            if f.dataset == 'products':
                if row['sku'] in skus:
                    err('sku', 'duplicate_sku', 'SKU already exists in the organization or upload.')
                skus.add(row['sku'])
            elif f.dataset == 'orders':
                if row['customer_id'] not in combined['customers']:
                    err('customer_id', 'unknown_customer', 'Customer must exist or be included in customers.csv.')
            elif f.dataset == 'order_lines':
                order = combined['orders'].get(row['order_id'])
                if not order:
                    err('order_id', 'unknown_order', 'Order must exist or be included in orders.csv.')
                elif order['status'] == 'cancelled':
                    err('order_id', 'cancelled_order', 'New lines on cancelled orders require review and are unsupported.')
                if row['product_id'] not in combined['products']:
                    err('product_id', 'unknown_product', 'Product must exist or be included in products.csv.')
            elif f.dataset == 'invoices':
                order = combined['orders'].get(row['order_id'])
                if not order:
                    err('order_id', 'unknown_order', 'Order must exist or be included in orders.csv.')
                elif row['invoice_date'] < order['order_date']:
                    err('invoice_date', 'date_order', 'Invoice date precedes the order date.')
                elif order['status'] == 'cancelled' and row['status'] == 'posted':
                    err('order_id', 'cancelled_order', 'A posted invoice cannot be imported against a cancelled order.')
            elif f.dataset == 'invoice_lines':
                inv = combined['invoices'].get(row['invoice_id'])
                ol = combined['order_lines'].get(row['order_line_id'])
                if not inv:
                    err('invoice_id', 'unknown_invoice', 'Invoice must exist or be included in invoices.csv.')
                if not ol:
                    err('order_line_id', 'unknown_order_line', 'Order line must exist or be included in order_lines.csv.')
                if (inv and inv['order_id'] != row['order_id']) or (ol and ol['order_id'] != row['order_id']):
                    err('order_id', 'order_mismatch', 'Invoice and order line must refer to this same order.')
                order = combined['orders'].get(row['order_id'])
                if inv and order and inv['status'] == 'posted' and order['status'] == 'cancelled':
                    err('order_id', 'cancelled_order', 'A posted invoice cannot be imported against a cancelled order.')
    # Sum all posted slices, including already-imported rows, before accepting more.
    quantities = {}
    for row in combined['invoice_lines'].values():
        inv = combined['invoices'].get(row['invoice_id'])
        if inv and inv['status'] == 'posted':
            key = row['order_line_id']
            quantities[key] = quantities.get(key, 0) + row['quantity']
    for f in report.files:
        if f.dataset != 'invoice_lines':
            continue
        for row in f.rows:
            ol = combined['order_lines'].get(row['order_line_id'])
            if ol and quantities.get(row['order_line_id'], 0) > ol['quantity']:
                report.error(f.file_name, row['_source_row'], 'quantity', 'overbilled_quantity', 'Combined posted invoice quantity exceeds the agreed order-line quantity.')
    if report.ok:
        for f in report.files:
            if f.dataset != 'invoice_lines':
                continue
            for row in f.rows:
                inv = combined['invoices'][row['invoice_id']]
                ol = combined['order_lines'][row['order_line_id']]
                if inv['status'] != 'posted':
                    continue
                amount = underbilling(row['quantity'], ol['agreed_net_unit_price'], row['invoiced_net_unit_price'])
                if amount > 0:
                    report.preview.append({'invoice_line_id': row['invoice_line_id'], 'quantity': row['quantity'],
                                           'agreed_net_unit_price': str(ol['agreed_net_unit_price']),
                                           'invoiced_net_unit_price': str(row['invoiced_net_unit_price']),
                                           'potential_loss': str(amount)})
    return report
