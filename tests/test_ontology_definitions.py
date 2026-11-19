from pathlib import Path
import yaml
from tools.ontology_definitions import definitions


def test_native_and_ossie_describe_snapshot_tables():
    native=yaml.safe_load(Path('integration/auto-ontology.yml').read_text())
    assert native == definitions()
    ossie=yaml.safe_load(Path('integration/ossie.yml').read_text())
    expected={'current_reviews','audit_results','policy_exclusions','reopened_summary'}
    assert {t['name'] for t in native['semantic_layer']['terms']} == expected
    assert {d['name'] for d in ossie['datasets']} == expected
