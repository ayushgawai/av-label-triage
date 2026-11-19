"""Portable correction jobs and transactional decision imports."""
import json
from pathlib import Path
from .core import connect, digest, record_review
from .ranking import classify


def export_job(workspace, incident, output, format, selected_images=None):
    if format not in ('coco','jsonl'): raise ValueError('format must be coco or jsonl')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);media=output.parent/'media';media.mkdir(exist_ok=True)
    with connect(workspace) as db:
        case=db.execute('SELECT * FROM incidents WHERE id=?',(incident,)).fetchone()
        if not case: raise ValueError('incident not found')
        images=[dict(r) for r in db.execute('SELECT * FROM images WHERE release_id=? ORDER BY id',(case['release_id'],))]
        annotations=[dict(r) for r in db.execute('SELECT * FROM source_annotations WHERE release_id=? ORDER BY id',(case['release_id'],))]
        proposals=[dict(r) for r in db.execute('SELECT * FROM proposals WHERE index_fingerprint=? ORDER BY image_id,id',(case['index_fingerprint'],))]
        events=[dict(r) for r in db.execute('SELECT * FROM review_events WHERE incident_id=? ORDER BY rowid',(incident,))]
    for p in proposals: p['bbox']=json.loads(p['bbox_json'])
    for a in annotations: a['bbox']=json.loads(a['bbox_json'])
    for im in images:
        meta=json.loads(im['metadata_json'])
        for n,box in enumerate(meta.get('ignore_regions',[])):annotations.append({'id':f"ignore:{im['id']}:{n}",'image_id':im['id'],'category':'ignore','bbox':box})
    metadata={im['id']:json.loads(im['metadata_json']) for im in images}
    duplicate=metadata[case['image_id']].get('duplicate_group')
    excluded={case['image_id']} | {image_id for image_id,meta in metadata.items() if duplicate and meta.get('duplicate_group')==duplicate}
    latest={e['proposal_id']:e['decision'] for e in events}
    eligible=[p for p in classify(proposals,annotations) if p['image_id'] not in excluded and p['policy_outcome']=='eligible' and p['match_status']!='already_labeled' and latest.get(p['id'],'unresolved') in ('unresolved','omission')]
    valid={p['image_id'] for p in eligible}
    chosen=valid if selected_images is None else set(map(str,selected_images))
    if not chosen or not chosen <= valid: raise ValueError('selection must contain eligible incident queue images')
    images=[im for im in images if im['id'] in chosen];annotations=[a for a in annotations if a['image_id'] in chosen and not a['id'].startswith('ignore:')];eligible=[p for p in eligible if p['image_id'] in chosen]
    cats=sorted({a['category'] for a in annotations}|{p['category'] for p in eligible});cat_ids={x:i+1 for i,x in enumerate(cats)};image_ids={im['id']:i+1 for i,im in enumerate(images)}
    image_records=[]
    for im in images:
        path=Path(im['path']);raw=path.read_bytes()
        if digest(raw)!=im['sha256']: raise ValueError('image hash mismatch')
        name=im['sha256']+path.suffix.lower();target=media/name
        if target.exists() and digest(target.read_bytes())!=im['sha256']: raise ValueError('media collision')
        if not target.exists(): target.write_bytes(raw)
        image_records.append({'id':image_ids[im['id']],'source_id':im['id'],'file_name':'media/'+name,'width':im['width'],'height':im['height'],'sha256':im['sha256'],'metadata':json.loads(im['metadata_json'])})
    def box(b):return [b[0],b[1],b[2]-b[0],b[3]-b[1]]
    originals=[{'id':i+1,'source_id':a['id'],'image_id':image_ids[a['image_id']],'category_id':cat_ids[a['category']],'bbox':box(a['bbox']),'area':(a['bbox'][2]-a['bbox'][0])*(a['bbox'][3]-a['bbox'][1]),'iscrowd':0} for i,a in enumerate(annotations)]
    suggestions=[]
    for p in eligible:
        history=[e for e in events if e['proposal_id']==p['id']]
        suggestions.append({'proposal_id':p['id'],'image_id':image_ids[p['image_id']],'source_image_id':p['image_id'],'category_id':cat_ids[p['category']],'bbox':box(p['bbox']),'score':p['score'],'model_revision':p['model_revision'],'match_status':p['match_status'],'reason_codes':json.loads(p['reason_codes_json']),'review_events':history})
    meta={'incident_id':incident,'release_id':case['release_id'],'policy_id':case['policy_id'],'index_fingerprint':case['index_fingerprint']}
    data={'info':meta,'images':image_records,'categories':[{'id':i,'name':x} for x,i in cat_ids.items()],'annotations':originals,'suggestions':suggestions}
    if format=='coco': text=json.dumps(data,sort_keys=True)+'\n'
    else: text=''.join(json.dumps({'info':meta,'image':im,'categories':data['categories'],'annotations':[a for a in originals if a['image_id']==im['id']],'suggestions':[a for a in suggestions if a['image_id']==im['id']]},sort_keys=True)+'\n' for im in image_records)
    temp=output.with_name(output.name+'.tmp');temp.write_text(text);temp.replace(output)
    return output


def import_decisions(workspace, path):
    events=[json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    db=connect(workspace)
    try:
        db.execute('BEGIN IMMEDIATE')
        for e in events:
            region=e.get('region');region=json.loads(e['region_json']) if region is None and e.get('region_json') else region
            record_review(workspace,e['incident_id'],e['proposal_id'],e['decision'],e['actor_type'],e['actor_id'],e['idempotency_key'],e['expected_revision'],e.get('supersedes_id'),region,_db=db)
        db.commit()
    except BaseException:
        db.rollback();raise
    finally: db.close()
    return len(events)
