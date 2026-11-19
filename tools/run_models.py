"""Run frozen per-image inference on an explicitly frozen list, never references."""
import argparse
import json
from pathlib import Path
import time
from PIL import Image, ImageOps
from avtriage.models import FrozenModels, contextual_crop, infer_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection', type=Path)
    parser.add_argument('images', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seed', type=Path, required=True, help='single disclosed development seed, not held-out references')
    args=parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    selection=json.loads(args.selection.read_text()); seeds=json.loads(args.seed.read_text())
    if len(seeds) != 1 or seeds[0]['image_id'] not in selection['dev']: raise ValueError('exactly one development seed required')
    started=time.monotonic(); model=FrozenModels('cpu'); missing=[]; manifest={}
    seed=seeds[0]
    with Image.open(args.images / (seed['image_id']+'.png')) as source:
        image=ImageOps.exif_transpose(source).convert('RGB')
        vector=model.embed([contextual_crop(image,seed['bbox'])])[0]
    for split in ('dev','eval'):
        for image_id in selection[split]:
            path=args.images / (image_id+'.png')
            if not path.exists(): missing.append(image_id); continue
            before=time.monotonic(); shard=infer_image(model,path,args.output/'shards')
            manifest[image_id]={'split':split,'fingerprint':shard['fingerprint'],'seconds':round(time.monotonic()-before,4),'count':len(shard['proposals'])}
            print(image_id,manifest[image_id]['count'],flush=True)
    payload={'selection':selection, 'seed_image_id':seed['image_id'], 'seed_bbox':seed['bbox'], 'seed_embedding':vector, 'images':manifest,'missing':missing,'elapsed_seconds':round(time.monotonic()-started,3),'device':'cpu','context':.2,'threshold':.05}
    temp=args.output/'manifest.tmp'; temp.write_text(json.dumps(payload,allow_nan=False,indent=2)+'\n'); temp.replace(args.output/'manifest.json')
    if missing: raise SystemExit(f'{len(missing)} images missing; rerun to resume')

if __name__ == '__main__': main()
