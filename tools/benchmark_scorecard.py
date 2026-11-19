#!/usr/bin/env python3
"""Run the package scorer from a frozen YAML config."""
import argparse
import json
from avtriage.benchmark_cli import run_config
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--config',required=True)
args=p.parse_args()
print(json.dumps(run_config(args.config),indent=2))
