# Release gate ledger

2026-11-19; current implementation is an experimental local research prototype, not an accepted release candidate.

- M0: KITTI/ReChecked inputs loaded privately and pinned upstream counts reproduced across 12 settings; official mapping mirror independently verified only against the devkit's published example. Full image cohort is not fully adjudicated. Secondary alignment status is documented in `data-feasibility.md`.
- M1: CPU fixture, local ingestion, review events and replay exist. Run `PYTHONPATH=. python tools/reproduce.py`; browser and accessibility coverage must be checked against the current build before claiming the full gate.
- M2: Actual local CPU models ran on a frozen drive-disjoint subset with one dev seed; see `evaluation.md` and `artifacts/reference/kitti-scorecard.json`. Two known evaluation omissions are insufficient for a general gain claim. No independent human pilot or review-time measurements; Flash provider and a blinded ambiguity evaluation remain outstanding.
- M3: Fixed stratified draws, blinded full-frame audit API/CLI, independent decisions, exact intervals, tiny exhaustive tests and seeded simulations exist. Human adjudication remains outstanding. Held-out scorecard tests known-reference reach and grouped conditional intervals; absent corrections are not negatives.
- M4: PostgreSQL snapshot and golden SQL were run on a synthetic fixture. A live NVIDIA Auto Ontology MCP query, semantic mapping import and negative causal-attribution evaluation are blocked on an authorized service and model endpoint; see `ontology.md`.
- M5: Root metadata, code license, notices, static Space files, CI, a pinned Python dependency lock and container build are prepared. A local wheel and Docker build were exercised; they must be rebuilt and rechecked against final source before distribution. Hosted publishing is not performed. Full clean-install, container launch, browser and license reviews remain release checks.
