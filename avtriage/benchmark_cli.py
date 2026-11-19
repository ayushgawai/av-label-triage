"""Opt-in private benchmark: read frozen outputs only in a separate scoring process."""
import csv
import json
import os
from pathlib import Path
import typer
import yaml
from .benchmark import scorecard, grouped_intervals
from .benchmark_reference import known_omissions
from .reference_compare import load_labels


def run_config(config):
    config=Path(config).resolve()
    cfg=yaml.safe_load(config.read_text())
    root=os.environ.get('AVTRIAGE_REFERENCE_ROOT')
    if not root: raise ValueError('set AVTRIAGE_REFERENCE_ROOT to the private cache root')
    def path(value):
        value=value.replace('${AVTRIAGE_REFERENCE_ROOT}',root)
        result=Path(value)
        return result if result.is_absolute() else config.parent/result
    ids=json.loads(path(cfg['split']).read_text())['val_imgs']
    orig,regions=load_labels(path(cfg['labels']),ids)
    with path(cfg['reference']).open(newline='') as f: refs=known_omissions(list(csv.DictReader(f)),orig,regions)
    manifest=json.loads(path(cfg['selection']).read_text()); eligible=manifest['eval']
    queues={name:json.loads(path(filename).read_text()) for name,filename in cfg['queues'].items()}
    result=scorecard(queues,json.loads(path(cfg['proposals']).read_text()),refs,eligible)
    known={r['image_id'] for r in refs}
    for name,filename in cfg.get('tile_queues',{}).items():
        ids=[r['image_id'] for r in json.loads(path(filename).read_text())]
        if len(set(ids)) != len(ids) or not set(ids) <= set(eligible): raise ValueError('invalid tile queue')
        result.setdefault('tile_search_hints',{})[name]=[{'budget':b,'reviewed_images':min(b,len(ids)),'known_images_reached':len(set(ids[:b]) & known)} for b in (25,50,100)]
    result['paired_drive_bootstrap']=grouped_intervals(queues,refs,eligible,manifest['drive_by_id'])
    return result


def register(app):
    @app.command('benchmark')
    def benchmark(config: Path = typer.Option(..., exists=True)):
        try: typer.echo(json.dumps(run_config(config),indent=2))
        except (ValueError,FileNotFoundError) as exc: raise typer.BadParameter(str(exc)) from exc
