#!/usr/bin/env python3
"""Convert local original KITTI labels and selected images to COCO JSON."""
import argparse
import json
from pathlib import Path
from PIL import Image


def convert(images, labels, selection, partition):
    ids = selection[partition]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate image ID')
    names = ['Car', 'Van', 'Truck', 'Pedestrian', 'Person_sitting', 'Cyclist', 'Tram', 'Misc', 'DontCare']
    category_ids = {name: n + 1 for n, name in enumerate(names)}
    out = {'images': [], 'categories': [{'id': v, 'name': k} for k, v in category_ids.items()], 'annotations': []}
    for image_id in ids:
        path = images / f'{image_id}.png'
        with Image.open(path) as image:
            width, height = image.size
            image.verify()
        out['images'].append({'id': image_id, 'file_name': path.name, 'width': width, 'height': height,
                              'metadata': {'drive_id': selection['drive_by_id'][image_id]}})
        for line_number, line in enumerate((labels / f'{image_id}.txt').read_text().splitlines()):
            parts = line.split()
            if len(parts) < 8 or parts[0] not in category_ids:
                raise ValueError(f'invalid KITTI label {image_id}:{line_number + 1}')
            x1, y1, x2, y2 = map(float, parts[4:8])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width, x2), min(height, y2)
            if x2 <= x1 or y2 <= y1:
                raise ValueError(f'empty clipped KITTI box {image_id}:{line_number + 1}')
            out['annotations'].append({'id': f'{image_id}:{line_number}', 'image_id': image_id,
                                       'category_id': category_ids[parts[0]], 'bbox': [x1, y1, x2-x1, y2-y1]})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--partition', choices=('dev', 'eval'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = convert(args.images, args.labels, json.loads(args.selection.read_text()), args.partition)
    args.output.write_text(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
