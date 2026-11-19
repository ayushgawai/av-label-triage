"""Deterministic annotation comparison and seed-conditioned image ranking."""
import math
import numpy as np


def overlap(a, b):
    x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = x * y
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / union if union > 0 else 0.0


def classify(proposals, annotations, match_iou=0.5, marginal_iou=0.1, min_height=0, ignore_ioa=0.5):
    """Greedy score-ordered one-to-one pedestrian matches, retaining conflicts."""
    used = set()
    out = []
    for p in sorted(proposals, key=lambda x: (-(x.get('score') or 0), x['image_id'], x['id'])):
        relevant = [a for a in annotations if a['image_id'] == p['image_id']]
        options = sorted(((overlap(p['bbox'], a['bbox']), a['id']) for a in relevant if a['category'] == 'pedestrian' and a['id'] not in used), key=lambda x: (-x[0], x[1]))
        best = options[0] if options else (0, None)
        cyclist = max((overlap(p['bbox'], a['bbox']) for a in relevant if a['category'] == 'cyclist'), default=0)
        area = (p['bbox'][2]-p['bbox'][0]) * (p['bbox'][3]-p['bbox'][1])
        ignored = any(max(0, min(p['bbox'][2],a['bbox'][2])-max(p['bbox'][0],a['bbox'][0])) * max(0, min(p['bbox'][3],a['bbox'][3])-max(p['bbox'][1],a['bbox'][1])) / area >= ignore_ioa for a in relevant if a['category'] in ('DontCare', 'ignore')) if area > 0 else False
        if p.get('category', 'pedestrian') != 'pedestrian' or p['bbox'][3]-p['bbox'][1] < min_height or ignored or area <= 0:
            status = 'out_of_scope'
        elif best[0] >= match_iou:
            used.add(best[1]); status = 'already_labeled'
        elif cyclist >= marginal_iou:
            status = 'cyclist_conflict'
        elif best[0] >= marginal_iou:
            status = 'marginal_overlap'
        elif any(overlap(p['bbox'], a['bbox']) >= match_iou for a in relevant if a['category'] == 'pedestrian' and a['id'] in used):
            status = 'crowded_conflict'
        else:
            status = 'unmatched'
        out.append({**p, 'match_status': status, 'match_iou': best[0], 'matched_annotation_id': best[1] if status == 'already_labeled' else None, 'policy_outcome': 'out_of_scope' if status == 'out_of_scope' else p.get('policy_outcome','eligible')})
    return sorted(out, key=lambda x: x['id'])


def rank(proposals, seed_vector, embeddings, *, method='fusion', excluded_images=(), rrf_k=60, max_per_group=None):
    """Rank one suggestion per image; embeddings maps proposal ID to normalized vector."""
    if method not in {'fusion', 'confidence', 'similarity'} or rrf_k <= 0:
        raise ValueError('invalid ranking method or constant')
    items = [p for p in proposals if p['image_id'] not in excluded_images and p.get('match_status', 'unmatched') != 'already_labeled' and p.get('policy_outcome', 'eligible') == 'eligible']
    if len({p['id'] for p in items}) != len(items):
        raise ValueError('duplicate proposal ID')
    norm = math.sqrt(sum(float(x)**2 for x in seed_vector))
    if not norm or not math.isfinite(norm):
        raise ValueError('invalid seed vector')
    present = [p for p in items if p['id'] in embeddings]
    sims = {}
    if present:
        matrix = np.asarray([embeddings[p['id']] for p in present], dtype=np.float64)
        seed = np.asarray(seed_vector, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] != len(seed): raise ValueError('embedding dimension mismatch')
        norms = np.linalg.norm(matrix, axis=1)
        if not np.isfinite(matrix).all() or not np.isfinite(norms).all() or np.any(norms == 0): raise ValueError('invalid embedding')
        with np.errstate(divide='ignore', over='ignore', invalid='ignore'):
            scores = (matrix / norms[:, None]) @ (seed / norm)
        if not np.isfinite(scores).all(): raise ValueError('nonfinite cosine result')
        sims = {p['id']: float(score) for p,score in zip(present,scores)}
    confidence_order = sorted((p for p in items if p.get('score') is not None), key=lambda p: (-p['score'], p['image_id'], p['id']))
    similarity_order = sorted((p for p in items if p['id'] in sims), key=lambda p: (-sims[p['id']], p['image_id'], p['id']))
    cr = {p['id']: i for i,p in enumerate(confidence_order,1)}
    sr = {p['id']: i for i,p in enumerate(similarity_order,1)}
    ranked = []
    for p in items:
        c, s = cr.get(p['id']), sr.get(p['id'])
        score = (1/(rrf_k+c) if c is not None and method in ('fusion','confidence') else 0) + (1/(rrf_k+s) if s is not None and method in ('fusion','similarity') else 0)
        ranked.append({**p, 'confidence_rank': c, 'similarity_rank': s, 'similarity': sims.get(p['id']), 'rank_score': score})
    ranked.sort(key=lambda p: (-p['rank_score'], p['image_id'], p['id']))
    seen = set(); unique = []; group_counts = {}
    for p in ranked:
        if p['image_id'] in seen: continue
        group = p.get('group_id')
        if group is not None and max_per_group is not None and group_counts.get(group, 0) >= max_per_group: continue
        p['overlapping_proposal_ids'] = sorted(q['id'] for q in ranked if q['image_id'] == p['image_id'] and overlap(p['bbox'], q['bbox']) >= 0.5)
        seen.add(p['image_id']); unique.append(p)
        if group is not None: group_counts[group] = group_counts.get(group,0) + 1
    return unique
