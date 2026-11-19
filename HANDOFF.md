# AV Label Triage — living handoff

Updated 2026-11-19, America/Los_Angeles. Current state is an experimental local prototype, not a completed release. See [release gate ledger](docs/release-status.md), [evaluation](docs/evaluation.md), [reference reproduction](docs/reference.md), [ontology](docs/ontology.md), and [data feasibility](docs/data-feasibility.md) for detailed evidence and limitations. Do not publish externally or pay for hardware without the maintainer's separate authorization.

## Ownership and active work

- Root agent: integration, final review, task coordination and handoff to user.
- Core agent: local review/audit/report/jobs UI, replay, Space build, package-data UI and browser verification.
- Data agent: model runs, leakage check, failure gallery, export exchange and model reproducibility.
- Reference agent: upstream reference, audit statistics, benchmark scoring, PostgreSQL/ontology prep, release files, wheel/container/CI checks and this handoff. Shared files change while agents are active; rebuild final artifacts after their last edits.

## Verified outcomes

- M0: official KITTI labels and pinned ReChecked commit are locally available; upstream code reproduced all 12 settings. Frozen 0.8/40/DontCare result: 42 overlooked, 87 misfitting. Original KITTI mapping was retrieved from a devkit mirror; byte comparison with authenticated official mapping remains open.
- M1: synthetic fixture, original-label import, append-only review, replay and local UI run. Fixture decisions are scripted, not humans. Browser smoke passed on an earlier build; repeat on final build.
- M2: CPU detector/DINO ran on 27 development and 133 held-out validation images partitioned by 58 source drives, with one dev seed and 44 eval drives. Two known held-out omissions: raw and eligible detector ceiling each 1/2; matched-box recovery 0 at 25/50/100 for confidence/similarity/fusion. Full-frame known-image reach and independent tile hints appear in [scorecard](artifacts/reference/kitti-scorecard.json). One seed and two known boxes cannot support a general gain claim. Fresh HF cache download and real-weight smoke succeeded. No human review-time or pilot claims.
- M3: independent image audit supports fixed strata, sampling without replacement, blind full-frame data, independent decisions and exact hypergeometric/Bonferroni bounds; unresolved decisions give sensitivity results. Tiny exhaustive and 1,000-seed simulations pass. Ranked outputs were reproduced with network and private reference tree blocked, not all filesystem reads blocked. See agent data notes for exact current evidence.
- M4: dedicated PostgreSQL fixture snapshot, three golden SQL queries, native + Ossie model definitions, pinned converter round-trip, and local MCP adapter fake transport tests run. Live authorized Auto Ontology import, readiness, ask_question, and actual response comparison remain blocked on an authorized service and model endpoint. Local vendor-provenance guard is not a live MCP test.
- M5: code license, notices, dataset card, Space metadata, lockfile, CI, Dockerfile and wheel prepared. Final clean wheel, container, Space and browser checks must follow active edits. A wheel from a prior snapshot reproduced the scorecard byte-for-byte from outside the checkout. No external publishing performed.

## Locations and commands

- Repo: `/Users/ayushgawai/Documents/GitHub/av-label-triage`; normal venv `.venv`, model venv `.model-venv`.
- Private cache: `/tmp/avtriage-reference` (ephemeral; copy to an external persistent location if needed). Contains `kitti/training/{label_2,image_2}`, `rechecked`, frozen `queues`, `tiles-v2`, and private seed JSON. No private images/corrections should enter the public bundle.
- Local Docker PostgreSQL: container `avtriage-m4-postgres`, loopback port 55438, test-only database `triage`. This is a dedicated disposable test instance, not production. See `docs/ontology.md`; export replaces snapshot rows.
- Offline CPU checks: `PYTHONPATH=. .venv/bin/python tools/reproduce.py` and `(cd viewer && npx playwright test)` after rebuilding the replay.
- Fresh private labels: `.venv/bin/python tools/reference_fetch.py /absolute/external/cache --images` (install `remotezip` for images). Pinned hashes and terms in `docs/reference.md`. Seed extraction command is documented there.
- Final benchmark from frozen outputs: `AVTRIAGE_REFERENCE_ROOT=/tmp/avtriage-reference .venv/bin/avtriage benchmark --config "$PWD/recipes/kitti-rechecked.yml"`. Compare JSON to `artifacts/reference/kitti-scorecard.json`; hash list is in `artifacts/reference/frozen-inputs.json`.
- Fixture/serve: `.venv/bin/avtriage demo --workspace /tmp/triage-demo`, then `.venv/bin/avtriage serve --workspace /tmp/triage-demo`. Model setup and empty-cache smoke commands are in README.
- PostgreSQL replay: `PYTHONPATH=. .venv/bin/python tools/ontology_fixture.py --dsn "$AVTRIAGE_POSTGRES_DSN"` against a **dedicated** database; live upstream MCP is separately gated.

## Next actions

1. Wait for core and data agents to finish; integrate and run full tests, rebuild `space/` and package static assets. Recheck frozen scorecard and reference isolation.
2. Rebuild wheel in `artifacts/release/`, clean-install outside the checkout, exercise normal CLI/UI and benchmark; rebuild locked Docker image, start default fixture and smoke it. Run browser tests against final output. Record versions, hashes and results in the release ledger.
3. Close honest remaining gates where independently possible: source-to-seed/model reproduction and failure gallery, review/audit UI, screenshot/replay and licensing QA. Keep human pilot, independent adjudication, production review timing, and live Auto Ontology marked incomplete until actually performed.
