"""Select private development seeds by the frozen rule; never inspect eval outcomes."""
import argparse
import csv
import json
from pathlib import Path
from avtriage.reference_compare import load_labels
from avtriage.benchmark_reference import known_omissions


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--labels',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--selection',type=Path,required=True)
    args=p.parse_args(); selection=json.loads(args.selection.read_text()); ids=selection['dev']
    originals,regions=load_labels(args.labels,ids)
    with args.reference.open(newline='') as f:
        rows=[r for r in csv.DictReader(f) if r['filename'].removesuffix('.png') in set(ids)]
    known=known_omissions(rows,originals,regions); by_image={}
    for r in known: by_image.setdefault(r['image_id'],r)
    chosen=[]; drives=set()
    for image_id in ids:
        drive=selection['drive_by_id'][image_id]
        if image_id in by_image and drive not in drives:
            chosen.append({'image_id':image_id, 'bbox':by_image[image_id]['bbox'], 'drive':drive}); drives.add(drive)
            if len(chosen)==3: break
    if not chosen: raise ValueError('no development seed found; documented dev-drive fallback requires separate mapping')
    print(json.dumps(chosen,indent=2))


if __name__=='__main__':main()
