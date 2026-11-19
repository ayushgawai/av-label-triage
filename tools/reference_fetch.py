#!/usr/bin/env python3
"""Fetch pinned public research inputs into an external directory; no redistribution."""
import argparse
import hashlib
import json
import subprocess
import urllib.request
import zipfile
from pathlib import Path


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('cache',type=Path)
    p.add_argument('--images',action='store_true',help='range-download frozen image members; requires remotezip')
    p.add_argument('--selection',type=Path,default=Path('recipes/kitti-image-selection.json'))
    args=p.parse_args(); cache=args.cache.resolve(); root=Path.cwd().resolve()
    if cache == root or root in cache.parents: raise ValueError('cache must be outside repository')
    cache.mkdir(parents=True,exist_ok=True)
    archive=cache/'data_object_label_2.zip'
    if not archive.exists(): urllib.request.urlretrieve('https://s3.eu-central-1.amazonaws.com/avg-kitti/data_object_label_2.zip',archive)
    if sha(archive)!='4efc76220d867e1c31bb980bbf8cbc02599f02a9cb4350effa98dbb04aaed880': raise ValueError('KITTI archive hash mismatch')
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('unsafe archive member')
        z.extractall(cache/'kitti')
    repo=cache/'rechecked'
    if not repo.exists(): subprocess.run(['git','clone','https://github.com/JonathanKlees/rechecked.git',str(repo)],check=True)
    subprocess.run(['git','-C',str(repo),'checkout','--detach','1321946698296416d0495999d000dec2deea5e4d'],check=True)
    for name,expected in [('validated_gt.csv','4a029e322ccacd281cf3158987f8cada9fb1e52fad9b605412f75681a3a8583f'),('train_val_split.json','9bbb95193c9f4f7ce2aa35e455c40b223b70702667844598538cee2abe470dd7')]:
        if sha(repo/'data'/name)!=expected: raise ValueError(name+' hash mismatch')
    if args.images:
        from remotezip import RemoteZip
        selection=json.loads(args.selection.read_text())
        with RemoteZip('https://s3.eu-central-1.amazonaws.com/avg-kitti/data_object_image_2.zip') as z:
            for image_id in selection['dev']+selection['eval']:
                if not image_id.isdigit() or len(image_id)!=6: raise ValueError('invalid image ID')
                z.extract('training/image_2/'+image_id+'.png',cache/'kitti')
    print('Pinned inputs ready in',cache)


if __name__=='__main__': main()
