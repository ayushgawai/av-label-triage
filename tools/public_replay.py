"""Record five public seed vectors and rankings from seeded source labels only."""
import json, hashlib
from pathlib import Path
from PIL import Image
from avtriage.models import FrozenModels, contextual_crop
from avtriage.ranking import classify, rank
def main():
    root=Path('assets/public/coco'); source=json.loads((root/'seeded-original.json').read_text()); seeds=json.loads((root/'seed-manifest.json').read_text()); shards={}
    for f in (root/'model-shards').glob('*.json'):
        d=json.loads(f.read_text()); shards[d['image_sha256']]=d
    anns=[]
    for a in source['annotations']:
        x,y,w,h=a['bbox'];anns.append({'id':str(a['id']),'image_id':str(a['image_id']),'category':'pedestrian' if a['category_id']==1 else 'other','bbox':[x,y,x+w,y+h]})
    proposals=[];embeddings={}
    for im in source['images']:
        path=root/im['file_name'];d=shards[hashlib.sha256(path.read_bytes()).hexdigest()]
        for i,p in enumerate(d['proposals']):
            pid=f"{im['id']}:{i}"; proposals.append({'id':pid,'image_id':str(im['id']),'bbox':p['bbox'],'score':p['score'],'category':'pedestrian'});embeddings[pid]=p['embedding']
    classified=classify(proposals,anns); model=FrozenModels('cpu'); replays=[]
    for seed in seeds:
        with Image.open(root/f"{seed['image_id']}.jpg") as image:
            x,y,w,h=seed['bbox']; vector=model.embed([contextual_crop(image.convert('RGB'),[x,y,x+w,y+h])])[0]
        replays.append({'seed':seed,'seed_embedding':vector,'queue':rank(classified,vector,embeddings,excluded_images=[str(seed['image_id'])])})
    (root/'recorded-replays.json').write_text(json.dumps({'label':'recorded inference; COCO boxes deliberately removed for a seeded demonstration','replays':replays},allow_nan=False,indent=2)+'\n')

if __name__ == '__main__': main()
