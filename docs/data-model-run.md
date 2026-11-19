# Frozen local model run, 2026-11-19

This run used original KITTI data and a single disclosed development seed, not hidden validation corrections. The local restricted files remain under `/tmp/avtriage-reference`; they are not public replay media. Run output is not a human pilot or a population-prevalence estimate.

Hardware: Apple M5 Pro, 15 logical CPUs, 24 GiB unified memory, macOS Darwin 25.6.0 arm64. Python 3.12.15, CPU, Torch 2.7.1, Transformers 4.52.4, Pillow 11.2.1, NumPy 2.2.6, safetensors 0.5.3. See `recipes/models.json` for model commits and frozen inference settings. Candidate score threshold 0.05; contextual crop expansion 20%; CLS vector; exact cosine; equal-weight RRF with k=60; one top result per image. DontCare excludes candidates with intersection over candidate area ≥0.5. Source annotation matching is greedy, confidence-ordered, one-to-one at IoU ≥0.5; marginal and cyclist/crowd conflicts remain reviewable. The detector emitted 4,378 person candidates on all 160 selected images, including 133 held-out evaluation images. The initial run took 104.674 seconds including loading models; images with zero candidates are retained in the population. There were 132 held-out images with at least one ranked eligible candidate. Primary indexing shard storage was approximately 34 MiB.

Thirty repeated primary fusion queries over preloaded held-out vectors took p50 33.224 ms and p95 44.117 ms, using nearest-rank p95, measured on this host. This excludes image decoding, inference, disk loading and seed embedding. NumPy's BLAS raised floating-point status warnings during the original run; all stored similarities were finite and 30 sampled scores agreed with scalar Python cosine within 1.12e-16. Current code checks finite outputs explicitly.

An independent tile pass searched 19 full-frame/overlapping regions per held-out image at scales 1, 2/3 and 1/2: 2,527 total. The tile pass took 45.56 seconds excluding model initialization; its one tile-only rank query took 28.2 ms, peak process RSS 512,999,424 bytes, and shard folder was approximately 21 MiB. These regions are search hints requiring a human-drawn final box, not detector localizations. A secondary combined queue includes 133 images, with one tile as its selected hint. The detector-only and tile-only queues remain separately available for comparisons. Failure cases, scoring and human adjudication are separate gates.

Reproduction with locally downloaded original KITTI and local disclosed single dev seed (substitute actual local paths; install the model extras and fetch pinned revisions first):

```sh
python -m tools.run_models recipes/kitti-image-selection.json "$KITTI_IMAGE_DIR" "$RUN_DIR/inference" --seed "$DEV_SEED_JSON"
python -m tools.reference_kitti --images "$KITTI_IMAGE_DIR" --labels "$KITTI_LABEL_DIR" --selection recipes/kitti-image-selection.json --partition eval --output "$RUN_DIR/eval-original.json"
python -m tools.rank_models "$RUN_DIR/inference/manifest.json" "$RUN_DIR/eval-original.json" "$RUN_DIR/queues"
python -m tools.run_tiles "$RUN_DIR/inference/manifest.json" "$KITTI_IMAGE_DIR" "$RUN_DIR/tiles"
python -m tools.fuse_tiles "$RUN_DIR/inference" "$RUN_DIR/queues/proposals.json" "$RUN_DIR/tiles" "$RUN_DIR/tiles/fusion.json"
```

Tile shards are atomically promoted and fingerprint image bytes, model revision, geometry, processor and device. Current tile and primary model cache fingerprints include Python and package versions; older v2 tile cache shards predate this addition and must be regenerated. Timing and JSON hashes vary with environment and run timings; compare rankings and input fingerprints, not manifest byte hashes alone.

Recorded original output hashes: primary confidence `f233e24b1aa6b78f7412820f60ce0cb9a5df7546c4984a5c45ba9284477844c4`, similarity `bef316cad93850a6b90523af24098ef1c41dd56044ca210c5da4c7e9346c616d`, fusion `fc7f0c909cb29db4116b54bcb7b3641057ab9a96a79a06d10de43f27f1bb41dd`; tile-only `81955e19b54b6669ba461a5b0c334d0f77e2fbfa7c86148fad4bca8d91f64864`, combined `ce0ed5669c9d73060115bfd040c5f59fcc56a6d08e2f1dca0a9fb669121a64c9` (SHA-256 of output JSON bytes). Reproducing these requires the exact selected images, seed and software; no guarantee of byte identity across hardware.

Public, differently licensed material: `assets/public/coco/` includes five COCO images, original human-produced annotations, deliberate seeded removals, actual model predictions and five recorded DINO seed/queue replays. `python -m tools.public_models` and `python -m tools.public_replay` recreate these with the pinned local model environment. See `assets/public/README.md` for image-specific licenses and attribution. These records are independent from the KITTI benchmark and from the separate Wikimedia image.

To prepare an empty Hugging Face cache independently (network download required):

```sh
uv venv --python 3.12 .model-venv
uv pip install --python .model-venv/bin/python -e '.[models]' 'Pillow==11.2.1' 'numpy==2.2.6'
HF_HOME=/path/to/new/cache .model-venv/bin/python -m tools.fetch_models
HF_HOME=/path/to/new/cache .model-venv/bin/python -c 'from avtriage.models import FrozenModels, infer_image; print(len(infer_image(FrozenModels("cpu"), "assets/public/coco/184324.jpg", "/tmp/avtriage-model-smoke")["proposals"]))'
```

On this host an initially empty `/tmp/avtriage-empty-hf` successfully fetched both pinned snapshots and the offline CPU smoke produced 72 candidates. The v3 tile rerun with software-versioned shard fingerprints took 46.70 seconds and 566,509,568 bytes peak RSS; its tile-only and combined queue hashes were byte-identical to the recorded v2 hashes above.

## Rank isolation and queue diagnostics

A second process was given copied source-only annotations, frozen seed vector and cached image shards in `/tmp/avtriage-isolated`; a macOS sandbox denied network and denied reading or writing `/private/tmp/avtriage-reference`, including the correction path. Independent probes confirmed both private-path reads and network connections raised `PermissionError`. All 132 proposal IDs and their order matched the original for each primary method. The process could still read other permitted filesystem paths, so this is not a mount-only container claim.

On the 133 held-out images, 3,494 raw detector candidates had these source-policy outcomes: 2,811 unmatched, 116 cyclist conflicts, 124 marginal overlaps, 39 crowded conflicts, 76 already labeled and 328 outside policy/ignore. These are machine routing outcomes, not human verdicts. Unique source drives in the first 25/50/100 images were: confidence 15/24/35, similarity 15/24/37, fusion 17/24/37. Every number is conditional on this frozen set and single seed.

For locally reproducible examples requiring human inspection, fusion image `002641` is routed as a cyclist conflict and `001822` as a marginal overlap. Open the original frames in `$KITTI_IMAGE_DIR/002641.png` and `$KITTI_IMAGE_DIR/001822.png`, and inspect their matching records in `$RUN_DIR/queues/fusion.json` with `$RUN_DIR/eval-original.json`. These are examples of ambiguous routes, not claims that the proposals are false alarms. Model-only zero-proposal image `005302` is absent from the detector queue but remains in the 133-image audit universe and the tile-search population. The private scorer's known-box results and failure to recover a corrected box by 100 images are in `artifacts/reference/kitti-scorecard.json`; the reference set is incomplete, so this does not establish total errors or precision.
