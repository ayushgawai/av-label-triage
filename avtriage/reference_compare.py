#!/usr/bin/env python3
"""Compare local KITTI labels with a private ReChecked CSV; no data is bundled."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def area(a):
    return (a[2] - a[0]) * (a[3] - a[1])


def iou(a, b):
    intersection = overlap(a, b)
    return intersection / (area(a) + area(b) - intersection)


def eligible(box, regions, height, filter_dc):
    return box[3] - box[1] >= height and (not filter_dc or all(overlap(box, dc) / area(box) < 0.5 for dc in regions))


def load_labels(label_dir, ids):
    originals, regions = defaultdict(list), defaultdict(list)
    for image_id in ids:
        path = label_dir / f'{image_id}.txt'
        if not path.is_file():
            raise FileNotFoundError(path)
        for line in path.read_text().splitlines():
            fields = line.split()
            if fields[0] in ('Pedestrian', 'DontCare'):
                box = tuple(map(float, fields[4:8]))
                if area(box) <= 0:
                    raise ValueError(f'invalid box in {path}')
                (originals if fields[0] == 'Pedestrian' else regions)[image_id + '.png'].append(box)
    return originals, regions


def compare(rows, originals, regions, probability=0.8, height=40, filter_dc=True):
    # ReChecked processes reference rows in input order and consumes originals only on IoU >= 0.5.
    available = {name: [box for box in boxes if eligible(box, regions[name], height, filter_dc)] for name, boxes in originals.items()}
    counts = Counter()
    for row in rows:
        if float(row['probability']) < probability or float(row['height']) < height:
            continue
        name = row['filename']
        box = tuple(float(row[k]) for k in ('xmin', 'ymin', 'xmax', 'ymax'))
        if area(box) <= 0:
            raise ValueError(f'invalid reference box in {name}')
        if not eligible(box, regions[name], 0, filter_dc):
            continue
        boxes = available.get(name, [])
        scores = [iou(box, other) for other in boxes]
        best = max(scores, default=0)
        if best >= 0.5:
            boxes.pop(scores.index(best))
            counts['matched'] += 1
        elif best > 0:
            counts['misfitting'] += 1
        else:
            counts['overlooked'] += 1
    return {key: counts[key] for key in ('matched', 'overlooked', 'misfitting')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', type=Path, required=True, help='KITTI training/label_2 directory')
    parser.add_argument('--reference', type=Path, required=True, help='private validated_gt.csv')
    parser.add_argument('--split', type=Path, required=True, help='pinned train_val_split.json')
    args = parser.parse_args()
    ids = json.loads(args.split.read_text())['val_imgs']
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate validation image IDs')
    originals, regions = load_labels(args.labels, ids)
    with args.reference.open(newline='') as f:
        rows = list(csv.DictReader(f))
    if not {row['filename'].removesuffix('.png') for row in rows} <= set(ids):
        raise ValueError('reference includes images outside validation split')
    result = []
    for dc in (False, True):
        for height in (0, 25, 40):
            for probability in (0.5, 0.8):
                result.append(dict(probability=probability, min_height=height, filter_dontcare=dc,
                                   **compare(rows, originals, regions, probability, height, dc)))
    print(json.dumps({'validation_images': len(ids), 'reference_rows': len(rows), 'results': result}, indent=2))


if __name__ == '__main__':
    main()
