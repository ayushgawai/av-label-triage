# AV Label Triage

A local investigation toolkit for reviewing possible missing pedestrian boxes and drawing an independent finite-population image audit. The owned fixture works offline; source data, model weights, and corrected labels stay local. The project is a research prototype: human validation, live Auto Ontology and several release gates remain open. See [evaluation](docs/evaluation.md), [reference reproduction](docs/reference.md), and [ontology status](docs/ontology.md).

## Install and run

Requires Python 3.12 or newer. In a virtual environment:

```sh
pip install -e '.[test]'
python -m pytest -q
avtriage demo --workspace ./triage-workspace
avtriage serve --workspace ./triage-workspace
```

Open the local address printed by the server. Fixture scenes and decisions labeled `scripted_fixture` are synthetic, not human reviews. `avtriage --help` lists import, indexing, review, audit and export commands; the audit blind view covers full frames and original annotations. The `space/` folder is a local static replay build; it is not published.

`tools/reference_compare.py` and `tools/benchmark_scorecard.py` are separate, opt-in evaluators. They require local KITTI and ReChecked inputs and frozen queues, and must not be used during mining. See [reproduction instructions](docs/reference.md). The held-out scorecard uses one seed and two known omissions, so it is exploratory and not a human precision result. [Audit methods and simulation](docs/evaluation.md) distinguish incomplete decisions from a finished estimate.

Original code is Apache-2.0; KITTI data and model weights have separate terms. KITTI is CC BY-NC-SA 3.0; consult the source terms before use or redistribution. Third-party input data and model artifacts are not granted the code license. See [data feasibility](docs/data-feasibility.md) and source-specific references for provenance.

To reproduce the held-out scorecard once private data and frozen model outputs are in the documented layout, set `AVTRIAGE_REFERENCE_ROOT` to that external cache and run `avtriage benchmark --config /absolute/path/to/recipes/kitti-rechecked.yml`. Relative paths in the recipe resolve against its directory. See [reference reproduction](docs/reference.md) for acquisition, frozen inputs and limitations. The tracked `artifacts/reference/kitti-scorecard.json` is an aggregate output, not the source images or corrected boxes.

For a local container: `docker build -t avtriage .` then `docker run --rm -p 8000:8000 avtriage`. It initializes a synthetic case before starting the server. Persist `/workspace` with a volume if decisions should survive container removal.

The real-weight CPU smoke is opt-in and downloads public model weights. From the repository root on Python 3.12:

```sh
python3.12 -m venv .model-venv
.model-venv/bin/pip install -e '.[models]'
HF_HOME=/tmp/avtriage-empty-hf .model-venv/bin/python -m tools.fetch_models
HF_HOME=/tmp/avtriage-empty-hf HF_HUB_OFFLINE=1 .model-venv/bin/python -m tools.model_smoke assets/public/coco/184324.jpg
```

Use an empty cache directory for a fresh-download check; the pinned revisions are in `recipes/models.json`. This downloads model weights and runs CPU inference; it is separate from normal fixture tests. The same check is available as a manual CI workflow.
