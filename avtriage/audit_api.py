"""Blind full-frame audit persistence and API."""
import json
import uuid
from fastapi import HTTPException
from pydantic import BaseModel
from .audit import draw, report
from .core import connect, canonical, digest, now


def create_design(workspace, incident_id, budget, seed, strata=None):
    with connect(workspace) as db:
        incident = db.execute('SELECT * FROM incidents WHERE id=?', (incident_id,)).fetchone()
        if not incident: raise ValueError('unknown incident')
        ids = [r['id'] for r in db.execute('SELECT id FROM images WHERE release_id=? ORDER BY id', (incident['release_id'],))]
        if strata is None:
            scores = {r['image_id']: r['score'] for r in db.execute('SELECT image_id, MAX(score) AS score FROM proposals WHERE index_fingerprint=? GROUP BY image_id', (incident['index_fingerprint'],))}
            strata = {i: ('zero' if i not in scores or scores[i] <= 0 else 'low' if scores[i] < 0.5 else 'high') for i in ids}
            # Adjacent bands are merged deterministically when every band cannot be sampled.
            order = ['zero', 'low', 'high']
            while len(set(strata.values())) > budget:
                present = [x for x in order if x in strata.values()]
                left, right = present[:2]
                strata = {i: (right if band == left else band) for i, band in strata.items()}
        if set(strata) != set(ids): raise ValueError('strata must cover exactly the release population')
        population = {}
        for i in ids: population.setdefault(str(strata[i]), []).append(i)
        design = draw(population, budget, seed)
        design_id = digest({'incident': incident_id, 'manifest': design['manifest_hash'], 'budget': budget, 'seed': seed})
        db.execute('INSERT OR IGNORE INTO audit_designs VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (design_id, incident['release_id'], incident_id, design['manifest_hash'], seed, canonical(population), canonical(strata), budget, incident['policy_id'], 'frozen', now()))
        for item in design['draws']:
            db.execute('INSERT OR IGNORE INTO audit_draws VALUES (?,?,?,?)', (design_id, item['image_id'], item['stratum'], item['inclusion_probability']))
        return {'design_id': design_id, 'sample_size': len(design['draws']), 'population': len(ids)}


def inspect(workspace, design_id):
    with connect(workspace) as db:
        design = db.execute('SELECT * FROM audit_designs WHERE id=?', (design_id,)).fetchone()
        if not design: raise ValueError('unknown design')
        images = []
        for row in db.execute('SELECT i.id,i.width,i.height FROM audit_draws d JOIN images i ON i.id=d.image_id AND i.release_id=? WHERE d.design_id=? ORDER BY i.id', (design['release_id'],design_id)):
            item = dict(row)
            item['annotations'] = [dict(a) for a in db.execute('SELECT id,category,bbox_json FROM source_annotations WHERE release_id=? AND image_id=? ORDER BY id', (design['release_id'],item['id']))]
            images.append(item)
        policy = db.execute('SELECT body_json FROM policies WHERE id=?', (design['policy_id'],)).fetchone()
        return {'design_id': design_id, 'release_id': design['release_id'], 'policy_id': design['policy_id'], 'policy': json.loads(policy['body_json']), 'images': images}


def decide(workspace, design_id, image_id, decision, actor_type, actor_id, supersedes_id=None):
    if decision not in ('omission', 'no_omission', 'unresolved') or actor_type not in ('human', 'human_adjudicator', 'scripted_fixture') or not actor_id:
        raise ValueError('invalid decision or actor')
    with connect(workspace) as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM audit_draws WHERE design_id=? AND image_id=?', (design_id,image_id)).fetchone(): raise ValueError('image not sampled')
        prior = db.execute('SELECT * FROM audit_decisions WHERE id=?', (supersedes_id,)).fetchone() if supersedes_id else None
        if supersedes_id and (not prior or prior['design_id'] != design_id or prior['image_id'] != image_id or (actor_type != 'human_adjudicator' and prior['actor_id'] != actor_id)):
            raise ValueError('invalid superseded decision')
        if supersedes_id and db.execute('SELECT 1 FROM audit_decisions WHERE supersedes_id=?', (supersedes_id,)).fetchone(): raise ValueError('decision already superseded')
        if not supersedes_id and db.execute('SELECT 1 FROM audit_decisions WHERE design_id=? AND image_id=? AND actor_id=? AND actor_type=?', (design_id,image_id,actor_id,actor_type)).fetchone():
            raise ValueError('actor must supersede prior decision')
        event_id = uuid.uuid4().hex
        db.execute('INSERT INTO audit_decisions VALUES (?,?,?,?,?,?,?,?)', (event_id,design_id,image_id,decision,actor_type,actor_id,supersedes_id,now()))
        return {'id':event_id}


def result(workspace, design_id):
    with connect(workspace) as db:
        design = db.execute('SELECT * FROM audit_designs WHERE id=?', (design_id,)).fetchone()
        if not design: raise ValueError('unknown design')
        draws = [dict(r) for r in db.execute('SELECT image_id,stratum,inclusion_probability FROM audit_draws WHERE design_id=?', (design_id,))]
        events = [dict(r) for r in db.execute('SELECT * FROM audit_decisions WHERE design_id=? ORDER BY rowid', (design_id,))]
        superseded = {e['supersedes_id'] for e in events if e['supersedes_id']}
        active = [e for e in events if e['id'] not in superseded]
        decisions = {}
        for d in draws:
            rows = [e for e in active if e['image_id'] == d['image_id']]
            adjudicated = [e for e in rows if e['actor_type'] == 'human_adjudicator']
            if adjudicated: rows = adjudicated
            values = {e['decision'] for e in rows}
            decisions[d['image_id']] = True if values == {'omission'} else False if values == {'no_omission'} else None
        return {**report({'population':json.loads(design['population_json']),'draws':draws}, decisions), 'sampled':len(draws), 'completed':sum(v is not None for v in decisions.values()), 'decision_events':len(events)}


class Design(BaseModel):
    incident_id: str
    budget: int
    seed: int
    strata: dict[str,str] | None = None

class Decision(BaseModel):
    image_id: str
    decision: str
    actor_type: str
    actor_id: str
    supersedes_id: str | None = None


def register(app, workspace):
    def call(fn, *args, **kwargs):
        try: return fn(*args, **kwargs)
        except ValueError as exc: raise HTTPException(409, str(exc)) from exc
    @app.post('/api/audits')
    def create(body: Design): return call(create_design, workspace, **body.model_dump())
    @app.get('/api/audits/{design_id}/blind')
    def blind(design_id: str): return call(inspect, workspace, design_id)
    @app.post('/api/audits/{design_id}/decisions')
    def decision(design_id: str, body: Decision): return call(decide, workspace, design_id, **body.model_dump())
    @app.get('/api/audits/{design_id}/result')
    def get_result(design_id: str): return call(result, workspace, design_id)
