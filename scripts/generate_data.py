"""Deterministic fictional distributor, no real company data. Run from project root."""
import csv
import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from marginguard.rules import underbilling

r = random.Random(42)
out = Path("data/synthetic")
out.mkdir(parents=True, exist_ok=True)
tables = {}
def add(table, **row):
    tables.setdefault(table, []).append(row)
def money(x):
    return Decimal(str(x)).quantize(Decimal("0.01"))
t = 'demo-distributor'
add('tenants', tenant_id=t, name='Piedmont Industrial Supply (Fictional)', currency='USD')
for i in range(1,41):
    add('customers', tenant_id=t, customer_id=f'C{i:03}', name=f'Demo Trade Customer {i:03}', payment_terms_days=r.choice([15,30,45]))
for i in range(1,61):
    cost = money(r.uniform(3,180))
    add('products', tenant_id=t, product_id=f'P{i:03}', sku=f'MG-{i:04}', category=r.choice(['Fasteners','Safety','Tools','Packaging']), standard_cost=cost, list_price=money(cost*Decimal('1.45')))
truth=[]
for i in range(1,501):
    oid=f'O{i:05}'
    day=date(2026,1,1)+timedelta(days=r.randrange(180))
    add('orders', tenant_id=t, order_id=oid, customer_id=r.choice(tables['customers'])['customer_id'], order_date=day, status='fulfilled')
    add('invoices', tenant_id=t, invoice_id=f'I{i:05}', order_id=oid, invoice_date=day+timedelta(days=r.randrange(1,5)), status='posted')
    for j in range(1,r.randint(2,5)):
        product=r.choice(tables['products']); lid=f'{oid}-L{j}'
        price=money(product['list_price']*r.choice([Decimal('1'),Decimal('.95'),Decimal('.9')]))
        qty=r.randint(1,75)
        add('order_lines', tenant_id=t, order_line_id=lid, order_id=oid, product_id=product['product_id'], quantity=qty, agreed_net_unit_price=price, unit_cost_snapshot=product['standard_cost'])
        scenario=r.choices(['clean','underbill','split_clean','overbill'],[82,10,6,2])[0]
        billed=money(price*Decimal('.90')) if scenario=='underbill' else money(price*Decimal('1.03')) if scenario=='overbill' else price
        parts=[qty//2,qty-qty//2] if scenario=='split_clean' and qty>1 else [qty]
        for k,q in enumerate(parts,1):
            iid=f'{lid}-B{k}'
            add('invoice_lines', tenant_id=t, invoice_line_id=iid, invoice_id=f'I{i:05}', order_id=oid, order_line_id=lid, quantity=q, invoiced_net_unit_price=billed)
            loss=underbilling(q,price,billed)
            truth.append(dict(invoice_line_id=iid,scenario=scenario,expected_underbilling=str(loss)))
    policy=r.choice(['pass_through','free_shipping','fixed_fee']); cost=money(r.uniform(12,150))
    add('freight_charges', tenant_id=t, freight_id=f'F{i:05}', order_id=oid, carrier=r.choice(['Demo Carrier A','Demo Carrier B']), carrier_cost=cost, customer_charge=cost if policy=='pass_through' else Decimal('0') if policy=='free_shipping' else Decimal('25'), policy=policy)
for i,line in enumerate(r.sample(tables['invoice_lines'],50),1):
    add('credits', tenant_id=t, credit_id=f'CR{i:04}', invoice_line_id=line['invoice_line_id'], issued_on=date(2026,8,1), amount=money(line['quantity']*line['invoiced_net_unit_price']*Decimal('.10')), reason='Documented partial return; not a duplicate-credit label')
for table,rows in tables.items():
    with (out/f'{table}.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
with (out/'ground_truth.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(truth[0])); writer.writeheader(); writer.writerows(truth)
manifest={'seed':42,'date_range':'2026-01-01 through 2026-08-01','currency':'USD','counts':{k:len(v) for k,v in tables.items()},'underbilling_cases':sum(Decimal(x['expected_underbilling'])>0 for x in truth),'expected_potential_loss':str(sum((Decimal(x['expected_underbilling']) for x in truth),Decimal('0')))}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
