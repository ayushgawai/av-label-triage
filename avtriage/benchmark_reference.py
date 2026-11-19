#!/usr/bin/env python3
"""Build a private known-omissions JSON from local inputs, then score a frozen queue."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from avtriage.reference_compare import eligible, iou, load_labels
from avtriage.benchmark import score


def known_omissions(rows, originals, regions):
    available = {name: [box for box in boxes if eligible(box, regions[name], 40, True)] for name, boxes in originals.items()}
    found = []
    for index, row in enumerate(rows):
        name = row['filename']
        if float(row['probability']) < .8 or float(row['height']) < 40:
            continue
        box = tuple(float(row[k]) for k in ('xmin','ymin','xmax','ymax'))
        if not eligible(box, regions[name], 0, True):
            continue
        boxes = available.get(name, [])
        scores = [iou(box, other) for other in boxes]
        best = max(scores, default=0)
        if best >= .5:
            boxes.pop(scores.index(best))
        elif best == 0:
            found.append({'id': str(index), 'image_id': name.removesuffix('.png'), 'bbox': box})
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--split', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--exclude', nargs='*', default=[])
    args = parser.parse_args()
    ids = json.loads(args.split.read_text())['val_imgs']
    orig, dc = load_labels(args.labels, ids)
    with args.reference.open(newline='') as f:
        refs = known_omissions(list(csv.DictReader(f)), orig, dc)
    selection = json.loads(args.selection.read_text())['eval']
    result = score(json.loads(args.queue.read_text()), refs, selection, excluded_images=args.exclude)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
