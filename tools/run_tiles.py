"""Independent multiscale DINO tile search; tiles are hints, not boxes."""
import argparse, hashlib, importlib.metadata, json, os, platform, resource, time
from pathlib import Path
from PIL import Image
from avtriage.models import FrozenModels, EMBEDDER_REVISION
from avtriage.ranking import rank

SCALES=(1.,2/3,1/2)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('manifest',type=Path);ap.add_argument('images',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    manifest=json.loads(args.manifest.read_text());output=args.output;output.mkdir(parents=True,exist_ok=True)
    model=FrozenModels('cpu');started=time.monotonic();proposals=[];embeddings={};shard_map={}
    for image_id,record in sorted(manifest['images'].items()):
        if record['split']!='eval': continue
        image_path=args.images/f'{image_id}.png';raw=image_path.read_bytes();config=json.dumps([EMBEDDER_REVISION,SCALES,'slow','cpu','tile-grid-v1',platform.python_version(),*[importlib.metadata.version(n) for n in ('torch','transformers','pillow','numpy')]],separators=(',',':')).encode();fingerprint=hashlib.sha256(raw+config).hexdigest();dest=output/(fingerprint+'.json');shard_map[image_id]=fingerprint
        if dest.exists(): data=json.loads(dest.read_text())
        else:
            with Image.open(image_path) as image:
                image=image.convert('RGB');width,height=image.size;boxes=[]
                for scale in SCALES:
                    w,h=width*scale,height*scale;positions=(0.,) if scale==1 else (0.,(1-scale)/2,1-scale)
                    boxes += [[x*width,y*height,x*width+w,y*height+h] for y in positions for x in positions]
                vectors=[]
                for offset in range(0,len(boxes),16): vectors.extend(model.embed([image.crop(box) for box in boxes[offset:offset+16]]))
                data=[{'bbox':box,'embedding':vec} for box,vec in zip(boxes,vectors)]
            tmp=dest.with_name(dest.name+f'.{os.getpid()}.tmp');tmp.write_text(json.dumps(data,allow_nan=False));os.replace(tmp,dest)
        for i,tile in enumerate(data):
            pid=hashlib.sha256(f'tile-v1:{image_id}:{i}'.encode()).hexdigest();proposals.append({'id':pid,'image_id':image_id,'bbox':tile['bbox'],'score':None,'source':'independent_tile'});embeddings[pid]=tile['embedding']
    query=time.monotonic();rows=rank(proposals,manifest['seed_embedding'],embeddings,method='similarity');query_seconds=time.monotonic()-query
    (output/'queue.json').write_text(json.dumps(rows,allow_nan=False,indent=2)+'\n');(output/'proposals.json').write_text(json.dumps(proposals,allow_nan=False)+'\n')
    (output/'run.json').write_text(json.dumps({'images':len(rows),'tiles':len(proposals),'elapsed_seconds':time.monotonic()-started,'query_seconds':query_seconds,'scales':SCALES,'model_revision':EMBEDDER_REVISION,'shards':shard_map,'peak_rss_platform_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'status':'tiles are image search hints, not localized boxes'},indent=2))
    print(len(rows),'images',len(proposals),'tiles')

if __name__=='__main__': main()
