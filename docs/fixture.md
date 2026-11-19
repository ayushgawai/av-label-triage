# Owned fixture and M1 reproduction

The fixture is generated entirely from deterministic geometric shapes in `avtriage.fixture`, with no external images. `truth.json` contains scripted cases and is not loaded by import or indexing. It is not a human annotation or benchmark result. Cases include an omission seed and duplicate, another omission/alternate seed, a labeled control, zero-proposal omission, signpost, shifted annotation, rider conflict and ignore region. The recorded proposals are scripted, not model inference. The local review surface does not yet implement the full conflict policy or audit interface.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest -q tests/test_core.py
.venv/bin/avtriage demo --workspace ./triage-workspace
.venv/bin/avtriage serve --workspace ./triage-workspace
```

Open http://127.0.0.1:8000, select the case and record a decision with your name. Restart the server and revisit it. The CLI output includes the incident ID. Export it with:

```sh
.venv/bin/avtriage export --workspace ./triage-workspace --incident INCIDENT_ID --format replay --output ./triage-workspace/exports/case.json
```

The output JSON uses relative paths to copied, SHA-256 checked media. The test exercises generated import, precomputed prediction index, seed, transactional review, restart through a new API instance, and replay IDs/media. To import customer data use `avtriage import coco --images DIR --annotations FILE --policy FILE --revision REV`; the policy YAML maps original category names in `categories` and prediction category IDs in `prediction_categories`. Index precomputed COCO prediction JSON with `avtriage index --release ID --predictions FILE --model-revision REV`; no model inference occurs. Release identity includes normalized source data, content hashes, policy and revision. Source media is copied into the workspace.
