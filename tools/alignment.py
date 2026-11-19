"""Pair two image directories; resized matches are suggestions requiring inspection."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps, ImageChops, ImageStat

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def inventory(root):
    records = []
    for path in sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS):
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert('RGB')
            digest = hashlib.sha256(f'{image.width}x{image.height}:RGB:'.encode() + image.tobytes()).hexdigest()
            thumb = image.resize((64, 64), Image.Resampling.LANCZOS)
            records.append({'path': str(path.relative_to(root)), 'size': list(image.size), 'hash': digest, 'thumb': thumb})
    return records


def pair(original, corrected, threshold=5.0):
    by_hash = defaultdict(list)
    for item in original:
        by_hash[item['hash']].append(item)
    rows = []
    for item in corrected:
        exact = by_hash[item['hash']]
        if exact:
            rows.append({'corrected': item['path'], 'status': 'exact' if len(exact) == 1 else 'ambiguous', 'candidates': [x['path'] for x in exact]})
            continue
        # shortcut: exhaustive 64x64 comparison can be slow for large datasets, add an index when needed.
        matches = []
        for candidate in original:
            rms = ImageStat.Stat(ImageChops.difference(item['thumb'], candidate['thumb'])).rms
            error = (sum(x*x for x in rms) / 3) ** 0.5
            if error <= threshold:
                matches.append({'path': candidate['path'], 'rms': round(error, 4), 'original_size': candidate['size'], 'corrected_size': item['size']})
        matches.sort(key=lambda x: (x['rms'], x['path']))
        rows.append({'corrected': item['path'], 'status': 'proposed_review' if len(matches) == 1 else 'ambiguous' if matches else 'unmatched', 'candidates': matches})
    # A shared source is not a one-to-one alignment and must not be silently accepted.
    uses = Counter(r['candidates'][0] if r['status'] == 'exact' else r['candidates'][0]['path'] for r in rows if r['status'] in ('exact', 'proposed_review'))
    for row in rows:
        if row['status'] in ('exact', 'proposed_review'):
            source = row['candidates'][0] if row['status'] == 'exact' else row['candidates'][0]['path']
            if uses[source] > 1:
                row['status'] = 'ambiguous'
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('corrected', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for directory in (args.original, args.corrected):
        if not directory.is_dir():
            parser.error(f'not a directory: {directory}')
    original, corrected = inventory(args.original), inventory(args.corrected)
    rows = pair(original, corrected)
    used = {r['candidates'][0] for r in rows if r['status'] == 'exact'}
    report = {'original_count': len(original), 'corrected_count': len(corrected), 'counts': dict(Counter(r['status'] for r in rows)), 'original_without_exact_match': len(original) - len(used), 'threshold_rms': 5.0, 'note': 'Only unique decoded-pixel hashes are exact. All resized candidates require geometry and visual review; no proposed pair is accepted.', 'pairs': rows}
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
