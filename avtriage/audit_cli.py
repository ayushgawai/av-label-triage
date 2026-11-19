"""CLI entry points for an independent full-frame audit."""
import json
from pathlib import Path
import typer
from .audit_api import create_design, inspect, decide, result


def register(app):
    audit = typer.Typer(no_args_is_help=True)
    app.add_typer(audit, name='audit')
    def show(value): typer.echo(json.dumps(value, sort_keys=True))
    @audit.command('create')
    def create(incident: str, budget: int, seed: int = 20261119, workspace: Path = Path('triage-workspace')):
        show(create_design(workspace, incident, budget, seed))
    @audit.command('blind')
    def blind(design: str, workspace: Path = Path('triage-workspace')): show(inspect(workspace, design))
    @audit.command('decide')
    def decision(design: str, image: str, decision: str, actor: str, actor_type: str = 'human', supersedes: str = '', workspace: Path = Path('triage-workspace')):
        show(decide(workspace, design, image, decision, actor_type, actor, supersedes or None))
    @audit.command('report')
    def audit_report(design: str, workspace: Path = Path('triage-workspace')): show(result(workspace, design))
