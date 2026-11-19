"""Freeze queues from source labels and inference shards, without corrected references."""
import argparse
import hashlib
import json
from pathlib import Path
from avtriage.ranking import classify, rank


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path); parser.add_argument('source_annotations',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); m=json.loads(args.manifest.read_text()); coco=json.loads(args.source_annotations.read_text())
    cats={v['id']:v['name'] for v in coco['categories']}; anns=[]
    mapping={'Pedestrian':'pedestrian','Cyclist':'cyclist','DontCare':'DontCare'}
    for a in coco['annotations']:
        x,y,w,h=a['bbox']; anns.append({'id':str(a['id']),'image_id':str(a['image_id']),'category':mapping.get(cats[a['category_id']],cats[a['category_id']]),'bbox':[x,y,x+w,y+h]})
    proposals=[]; embeddings={}; args.output.mkdir(parents=True,exist_ok=True)
    drives={str(x['id']): x.get('metadata',{}).get('drive_id') for x in coco['images']}
    for image_id,im in sorted(m['images'].items()):
        if im['split'] != 'eval': continue
        shard=json.loads((args.manifest.parent/'shards'/(im['fingerprint']+'.json')).read_text())
        for i,p in enumerate(shard['proposals']):
            pid=hashlib.sha256(f"{im['fingerprint']}:{i}".encode()).hexdigest()
            proposals.append({'id':pid,'image_id':image_id,'bbox':p['bbox'],'score':p['score'],'category':'pedestrian','group_id':drives.get(image_id),'source_model_revision':shard['detector_revision']})
            embeddings[pid]=p['embedding']
    classified=classify(proposals,anns)
    (args.output/'proposals.json').write_text(json.dumps(classified,allow_nan=False,indent=2)+'\n')
    for method in ('confidence','similarity','fusion'):
        result=rank(classified,m['seed_embedding'],embeddings,method=method,excluded_images=[m['seed_image_id']])
        (args.output/(method+'.json')).write_text(json.dumps(result,allow_nan=False,indent=2)+'\n')
        print(method,len(result),flush=True)
    (args.output/'run.json').write_text(json.dumps({'manifest_sha256':hashlib.sha256(args.manifest.read_bytes()).hexdigest(),'source_annotations_sha256':hashlib.sha256(args.source_annotations.read_bytes()).hexdigest(),'proposal_count':len(proposals),'eligible_proposals':sum(p['policy_outcome']=='eligible' and p['match_status']!='already_labeled' for p in classified),'methods':['confidence','similarity','fusion'],'rrf_k':60,'seed_image_id':m['seed_image_id'],'reference_used':False},indent=2)+'\n')

if __name__ == '__main__': main()
