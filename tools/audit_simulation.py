#!/usr/bin/env python3
"""Preseeded finite-population simulation; synthetic truth only."""
import json
import random
from functools import lru_cache
from statistics import median
from avtriage import audit

original_interval = audit.interval
audit.interval = lru_cache(maxsize=None)(original_interval)
scenarios = {
    'all_negative': (0, 0, 0),
    'concentrated': (0, 0, 30),
    'rare_low_score': (3, 0, 0),
    'unequal': (2, 10, 15),
    'duplicate_looking_groups': (50, 20, 15),
    'near_census': (2, 10, 15),
}
results = {}
for name, positives in scenarios.items():
    groups = {'low': [f'l{i}' for i in range(100)], 'mid': [f'm{i}' for i in range(40)], 'high': [f'h{i}' for i in range(30)]}
    truth = {item: j < k for (_, ids), k in zip(groups.items(), positives) for j, item in enumerate(ids)}
    true_rate = sum(truth.values()) / len(truth)
    estimates, widths, covered = [], [], 0
    for seed in range(1000):
        design = audit.draw(groups, 165 if name == 'near_census' else 40, seed)
        result = audit.report(design, {d['image_id']: truth[d['image_id']] for d in design['draws']})
        estimates.append(result['estimate']); widths.append(result['upper'] - result['lower'])
        covered += result['lower'] <= true_rate <= result['upper']
    coverage = covered / 1000
    results[name] = {'truth': true_rate, 'mean_bias': sum(estimates)/1000-true_rate,
                     'median_width': median(widths), 'coverage': coverage,
                     'coverage_wilson_95': [(coverage + 1.96**2/2000 - 1.96*((coverage*(1-coverage)/1000 + 1.96**2/(4*1000**2))**.5))/(1+1.96**2/1000), (coverage + 1.96**2/2000 + 1.96*((coverage*(1-coverage)/1000 + 1.96**2/(4*1000**2))**.5))/(1+1.96**2/1000)]}
print(json.dumps({'seeds': '0..999', 'draws_per_scenario': 1000, 'population_sizes': [100, 40, 30], 'budget': '40 except near_census 165', 'results': results}, indent=2))
