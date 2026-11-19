"""Freeze secondary proposal-plus-tile queue without corrected references."""
import argparse, hashlib, json
from pathlib import Path
from avtriage.ranking import rank

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('inference',type=Path);ap.add_argument('proposal_file',type=Path);ap.add_argument('tiles',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
 m=json.loads((args.inference/'manifest.json').read_text());proposals=json.loads(args.proposal_file.read_text());tile_run=json.loads((args.tiles/'run.json').read_text());embeddings={}
 for image_id,im in m['images'].items():
  if im['split']!='eval': continue
  shard=json.loads((args.inference/'shards'/(im['fingerprint']+'.json')).read_text())
  for i,p in enumerate(shard['proposals']): embeddings[hashlib.sha256(f"{im['fingerprint']}:{i}".encode()).hexdigest()]=p['embedding']
  tiles=json.loads((args.tiles/(tile_run['shards'][image_id]+'.json')).read_text())
  for i,t in enumerate(tiles):
   pid=hashlib.sha256(f'tile-v1:{image_id}:{i}'.encode()).hexdigest();proposals.append({'id':pid,'image_id':image_id,'bbox':t['bbox'],'score':None,'source':'independent_tile'});embeddings[pid]=t['embedding']
 rows=rank(proposals,m['seed_embedding'],embeddings,method='fusion');args.output.write_text(json.dumps(rows,allow_nan=False,indent=2)+'\n');print('combined images',len(rows),'tile hints',sum(r.get('source')=='independent_tile' for r in rows))

if __name__=='__main__':main()
