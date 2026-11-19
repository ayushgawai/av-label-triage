"""Populate dedicated PostgreSQL with repeatable synthetic fixture, then check goldens."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import psycopg
from avtriage.fixture import demo
from avtriage.core import connect, record_review
from avtriage.audit_api import create_design, inspect, decide


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsn',required=True,help='dedicated database; snapshot tables are replaced')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        case=demo(Path(directory)); incident=case['incident_id']
        with connect(directory) as db: proposals=[r[0] for r in db.execute('SELECT id FROM proposals ORDER BY id LIMIT 2')]
        for j,decision in enumerate(('omission','out_of_scope')):
            record_review(directory,incident,proposals[j],decision,'scripted_fixture','fixture',f'm4-{j}',0)
        design=create_design(directory,incident,2,44)['design_id']
        for j,image in enumerate(inspect(directory,design)['images']):
            decide(directory,design,image['id'],'omission' if j==0 else 'no_omission','scripted_fixture','fixture')
        subprocess.run([sys.executable,'tools/postgres_export.py','--workspace',directory,'--dsn',args.dsn],check=True)
        with psycopg.connect(args.dsn) as db:
            reopened=db.execute('SELECT reopened_images FROM avtriage.reopened_summary').fetchone()[0]
            audit=db.execute('SELECT population,sampled,completed,status,estimate FROM avtriage.audit_results').fetchone()
            excluded=db.execute('SELECT count(*) FROM avtriage.policy_exclusions').fetchone()[0]
            assert reopened==1 and excluded==1 and audit[:4]==(9,2,2,'complete') and abs(audit[4]-1/9)<1e-12
            print(json.dumps({'reopened_images':reopened,'audit':list(audit),'excluded_images':excluded}))


if __name__=='__main__':main()
