"""Independent scorer for ranked suggestions and private known-omission boxes."""
from avtriage.ranking import overlap


def score(queue, reference, eligible_images, budgets=(25, 50, 100), excluded_images=()):
    eligible, excluded = set(eligible_images), set(excluded_images)
    if len(eligible) != len(eligible_images) or not excluded <= eligible:
        raise ValueError('invalid eligible or excluded image IDs')
    if len({p['image_id'] for p in queue}) != len(queue):
        raise ValueError('queue must contain at most one item per image')
    if any(p['image_id'] not in eligible or p['image_id'] in excluded for p in queue):
        raise ValueError('queue contains an ineligible or excluded image')
    if len({r['id'] for r in reference}) != len(reference):
        raise ValueError('reference IDs must be unique')
    refs = [r for r in reference if r['image_id'] in eligible and r['image_id'] not in excluded]
    hits, records = set(), []
    for p in queue:
        choices = sorted(((overlap(p['bbox'], r['bbox']), r['id']) for r in refs
                          if r['image_id'] == p['image_id'] and r['id'] not in hits), key=lambda x: (-x[0], x[1]))
        if choices and choices[0][0] >= .5:
            hits.add(choices[0][1]); records.append(choices[0][1])
        else:
            records.append(None)
    result = []
    for budget in budgets:
        if budget <= 0:
            raise ValueError('budgets must be positive')
        reviewed = min(budget, len(queue))
        found = len({x for x in records[:reviewed] if x is not None})
        result.append({'budget': budget, 'reviewed_images': reviewed, 'known_boxes_recovered': found,
                       'known_images_reached': len({p['image_id'] for p in queue[:reviewed]} & {r['image_id'] for r in refs}),
                       'known_recovery_per_reviewed_image': found / reviewed if reviewed else None})
    return {'eligible_images': len(eligible - excluded), 'known_boxes': len(refs), 'budgets': result,
            'interpretation': 'Known reference recovery only; unmatched items are unadjudicated, not confirmed negatives.'}


def scorecard(queues, proposals, reference, eligible_images, seed=20261119, budgets=(25, 50, 100)):
    """Compare frozen candidate queues and a full-frame random baseline at image budgets."""
    import random
    eligible = sorted(set(eligible_images))
    if len(eligible) != len(eligible_images): raise ValueError('duplicate eligible image')
    if any(p['image_id'] not in eligible for p in proposals): raise ValueError('proposal outside population')
    known_images = {r['image_id'] for r in reference if r['image_id'] in eligible}
    random_order = random.Random(seed).sample(eligible, len(eligible))
    baseline = []
    for budget in budgets:
        selected = random_order[:budget]
        found = len(set(selected) & known_images)
        baseline.append({'budget':budget, 'reviewed_images':len(selected), 'known_images_reached':found})
    def reached(items):
        return {r['id'] for p in items for r in reference if p['image_id'] == r['image_id'] and overlap(p['bbox'], r['bbox']) >= .5}
    raw_refs = reached(proposals)
    eligible_refs = reached([p for p in proposals if p.get('policy_outcome', 'eligible') == 'eligible' and p.get('match_status') != 'already_labeled'])
    return {'random_full_frame': baseline,
            'raw_detector_ceiling_known_boxes': len(raw_refs),
            'eligible_proposal_ceiling_known_boxes': len(eligible_refs),
            'known_boxes': len([r for r in reference if r['image_id'] in eligible]),
            'candidate_methods': {name: score(queue, reference, eligible, budgets) for name, queue in queues.items()},
            'note': 'Image reach assumes full-frame inspection; box recovery requires IoU >= 0.5. Neither establishes human-confirmed precision.'}


def grouped_intervals(queues, reference, eligible_images, drive_by_id, budgets=(25,50,100), seed=20261119, replicates=2000):
    """Paired drive bootstrap of fixed-queue known-image counts, conditional on this cohort."""
    import random
    groups = sorted({drive_by_id[i] for i in eligible_images})
    if len(groups) < 2: raise ValueError('at least two drives required')
    truth = {r['image_id'] for r in reference} & set(eligible_images)
    rng = random.Random(seed)
    boot = [[rng.choice(groups) for _ in groups] for _ in range(replicates)]
    out = []
    for budget in budgets:
        reached = {name: {p['image_id'] for p in queue[:budget]} & truth for name, queue in queues.items()}
        for name in sorted(reached):
            if name == 'confidence' or 'confidence' not in reached: continue
            contributions = {g: sum(drive_by_id[i] == g for i in reached[name]) - sum(drive_by_id[i] == g for i in reached['confidence']) for g in groups}
            values = sorted(sum(contributions[g] for g in sample) for sample in boot)
            out.append({'method':name, 'comparator':'confidence', 'budget':budget,
                        'observed_difference':sum(contributions.values()),
                        'percentile_95':[values[int(.025*(replicates-1))],values[int(.975*(replicates-1))]]})
    return {'groups':len(groups), 'replicates':replicates, 'seed':seed, 'comparisons':out,
            'interpretation':'Conditional fixed-queue drive bootstrap of known-image count difference; sparse truth and one seed preclude a general gain claim.'}
