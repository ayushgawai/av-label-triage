import json
import pytest
from avtriage.core import connect
from avtriage.exchange import export_job, import_decisions
from avtriage.fixture import demo

def test_portable_job_and_atomic_reimport(tmp_path):
    ids=demo(tmp_path); job=tmp_path/'job'/'annotations.json';export_job(tmp_path,ids['incident_id'],job,'coco');data=json.loads(job.read_text())
    assert data['annotations'] and data['suggestions']
    assert all(isinstance(a['id'],int) for a in data['annotations'])
    assert all(i['source_id'] != '0' for i in data['images'])
    assert all((job.parent/i['file_name']).is_file() for i in data['images'])
    assert all(a['source_id'] for a in data['annotations'])
    jsonl=tmp_path/'job'/'job.jsonl';export_job(tmp_path,ids['incident_id'],jsonl,'jsonl')
    assert len(jsonl.read_text().splitlines()) == len(data['images'])
    p=data['suggestions'][0]
    subset=tmp_path/'subset'/'job.json';export_job(tmp_path,ids['incident_id'],subset,'coco',[p['source_image_id']]);assert len(json.loads(subset.read_text())['images'])==1
    with pytest.raises(ValueError): export_job(tmp_path,ids['incident_id'],subset,'coco',['0'])
    e={'incident_id':ids['incident_id'],'proposal_id':p['proposal_id'],'decision':'omission','actor_type':'human','actor_id':'reviewer','idempotency_key':'first','expected_revision':0,'supersedes_id':None}
    inp=tmp_path/'decisions.jsonl';inp.write_text(json.dumps(e)+'\n'+json.dumps({**e,'proposal_id':'missing','idempotency_key':'second'})+'\n')
    with pytest.raises(ValueError): import_decisions(tmp_path,inp)
    with connect(tmp_path) as db: assert db.execute('SELECT count(*) FROM review_events').fetchone()[0] == 0
    inp.write_text(json.dumps(e)+'\n');assert import_decisions(tmp_path,inp)==1;assert import_decisions(tmp_path,inp)==1
    with connect(tmp_path) as db:
        assert db.execute('SELECT count(*) FROM review_events').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM source_annotations').fetchone()[0] == sum(1 for _ in db.execute('SELECT id FROM source_annotations'))
