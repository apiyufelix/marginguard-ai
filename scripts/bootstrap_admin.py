"""Local operator command: grant a company's first admin to an exact account UUID."""
import argparse
from uuid import UUID
from sqlalchemy import text
from marginguard.db import get_engine
from marginguard.access import set_membership


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--user-id', required=True, type=UUID)
    args = parser.parse_args()
    engine = get_engine()
    with engine.connect() as conn:
        print('Database:',conn.execute(text('SELECT current_database()')).scalar_one())
        print('Company:',conn.execute(text('SELECT name FROM tenants WHERE tenant_id=:t'),{'t':args.tenant}).scalar_one())
        row = conn.execute(text('SELECT display_name,email FROM app_users WHERE user_id=:u'),{'u':args.user_id}).one()
        print('Account:',args.user_id, row.display_name, row.email or '')
    if input('Type GRANT to create this first Admin membership: ').strip() != 'GRANT':
        print('No changes made.')
        return
    set_membership(engine,args.tenant,args.user_id,'admin',True,bootstrap=True)
    print('First Admin membership created. Refresh MarginGuard.')


if __name__ == '__main__':
    main()
