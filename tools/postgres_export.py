#!/usr/bin/env python3
"""Replace one local workspace's vetted Postgres snapshot; never exports references."""
import argparse
from pathlib import Path
import psycopg
from avtriage.core import connect
from avtriage.audit_api import result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True); p.add_argument('--dsn',required=True)
    args=p.parse_args()
    with connect(args.workspace) as db, psycopg.connect(args.dsn) as pg:
        pg.execute(Path('integration/schema.sql').read_text())
        # This destination is a dedicated snapshot, replaced atomically in one transaction.
        pg.execute('TRUNCATE avtriage.review_events, avtriage.audit_results')
        for row in db.execute('SELECT r.id,i.release_id,r.incident_id,r.image_id,r.policy_id,r.decision,r.actor_type,r.supersedes_id FROM review_events r JOIN incidents i ON i.id=r.incident_id'):
            pg.execute('INSERT INTO avtriage.review_events VALUES (%s,%s,%s,%s,%s,%s,%s,%s)', tuple(row))
        for row in db.execute('SELECT * FROM audit_designs'):
            a=result(args.workspace,row['id'])
            population=sum(map(len,__import__('json').loads(row['population_json']).values()))
            pg.execute('INSERT INTO avtriage.audit_results VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                       (row['id'],row['release_id'],row['incident_id'],row['policy_id'],population,a['sampled'],a['completed'],a['status'],a.get('estimate'),a.get('lower'),a.get('upper')))
    print('Snapshot exported to dedicated avtriage schema.')


if __name__=='__main__': main()
