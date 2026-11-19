"""Create seeded COCO inputs and recorded inference; COCO boxes are never model inputs."""
import json
from pathlib import Path
from avtriage.models import FrozenModels, infer_image

def main():
    root=Path('assets/public/coco'); source=json.loads((root/'annotations.json').read_text()); seeds=[]
    for image in source['images']:
        candidates=[a for a in source['annotations'] if a['image_id']==image['id'] and a['category_id']==1 and a['iscrowd']==0]
        if candidates:
            chosen=max(candidates,key=lambda a:(a['bbox'][3],-a['id']))
            seeds.append({'image_id':image['id'],'annotation_id':chosen['id'],'bbox':chosen['bbox'],'label':'seeded removal of original COCO person annotation'})
    removed={x['annotation_id'] for x in seeds}; original={**source,'annotations':[a for a in source['annotations'] if a['id'] not in removed]}
    (root/'seeded-original.json').write_text(json.dumps(original,indent=2)+'\n'); (root/'seed-manifest.json').write_text(json.dumps(seeds,indent=2)+'\n')
    model=FrozenModels('cpu'); outputs=[]
    for image in source['images']:
        result=infer_image(model,root/image['file_name'],root/'model-shards')
        for p in result['proposals']:
            x1,y1,x2,y2=p['bbox'];outputs.append({'image_id':image['id'],'category_id':1,'bbox':[x1,y1,x2-x1,y2-y1],'score':p['score']})
        print(image['id'],len(result['proposals']),flush=True)
    (root/'predictions.json').write_text(json.dumps(outputs,indent=2)+'\n')

if __name__ == '__main__': main()
