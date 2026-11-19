"""Finite-population stratified audit, independent of review queue decisions."""
import hashlib
import json
import math
import random


def draw(population, budget, seed):
    """population maps stratum names to image IDs. Every nonempty stratum is sampled."""
    groups = {str(k): sorted(v) for k, v in population.items() if v}
    ids = [item for group in groups.values() for item in group]
    if len(set(ids)) != len(ids):
        raise ValueError('image IDs must be unique across strata')
    if not groups or not len(groups) <= budget <= len(ids):
        raise ValueError('budget must cover every nonempty stratum and not exceed population')
    sizes = {k: 1 for k in groups}
    while sum(sizes.values()) < budget:
        # Allocate remaining places proportionally, with deterministic ties.
        k = min((k for k in groups if sizes[k] < len(groups[k])),
                key=lambda k: (sizes[k] / len(groups[k]), k))
        sizes[k] += 1
    rng = random.Random(seed)
    draws = []
    for k in sorted(groups):
        for image_id in sorted(rng.sample(groups[k], sizes[k])):
            draws.append({'image_id': image_id, 'stratum': k, 'inclusion_probability': sizes[k] / len(groups[k])})
    manifest = json.dumps(groups, sort_keys=True, separators=(',', ':')).encode()
    return {'population': groups, 'budget': budget, 'seed': seed,
            'manifest_hash': hashlib.sha256(manifest).hexdigest(), 'draws': draws}


def _tail(N, K, n, x, upper):
    lo, hi = max(0, n - (N - K)), min(n, K)
    if upper:
        lo = max(lo, x)
    else:
        hi = min(hi, x)
    return sum(math.comb(K, i) * math.comb(N - K, n - i) for i in range(lo, hi + 1)) / math.comb(N, n)


def interval(N, n, x, alpha=0.05):
    """Equal-tailed exact hypergeometric inversion for an unknown finite count."""
    if not (0 <= x <= n <= N and N > 0 and n > 0 and 0 < alpha < 1):
        raise ValueError('invalid stratum counts or alpha')
    def first_true(predicate):
        lo, hi = x, N - n + x
        while lo < hi:
            mid = (lo + hi) // 2
            if predicate(mid):
                hi = mid
            else:
                lo = mid + 1
        return lo
    lower = first_true(lambda K: _tail(N, K, n, x, True) > alpha / 2)
    # P(X <= x) decreases in K; find first excluded count.
    lo, hi = x, N - n + x + 1
    while lo < hi:
        mid = (lo + hi) // 2
        if mid > N - n + x or _tail(N, mid, n, x, False) <= alpha / 2:
            hi = mid
        else:
            lo = mid + 1
    return lower, lo - 1


def report(design, decisions, confidence=0.95):
    """Decisions map sampled IDs to True, False, or None; unresolved bounds are sensitivity results."""
    groups, draws = design['population'], design['draws']
    selected = {d['image_id'] for d in draws}
    if len(selected) != len(draws) or set(decisions) - selected:
        raise ValueError('decisions must refer to unique sampled images')
    if any(v is not True and v is not False and v is not None for v in decisions.values()):
        raise ValueError('decisions must be true, false, or null')
    total = sum(map(len, groups.values()))
    alpha = (1 - confidence) / len(groups)
    def calculate(unknown):
        estimate = lower = upper = 0
        for k, ids in groups.items():
            sample = [d['image_id'] for d in draws if d['stratum'] == k]
            if not sample or not set(sample) <= set(ids):
                raise ValueError('invalid draw')
            x = sum(unknown if decisions.get(i) is None else decisions[i] for i in sample)
            N, n = len(ids), len(sample)
            low, high = interval(N, n, x, alpha)
            estimate += N * x / n
            lower += low
            upper += high
        return {'estimate': estimate / total, 'lower': lower / total, 'upper': upper / total}
    unresolved = sum(decisions.get(i) is None for i in selected)
    if unresolved:
        return {'status': 'unresolved', 'unresolved': unresolved, 'all_unknown_negative': calculate(False), 'all_unknown_positive': calculate(True)}
    return {'status': 'complete', 'unresolved': 0, **calculate(False)}
