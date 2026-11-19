# Data and model feasibility (2026-11-19)

This is an availability inventory, not a completed benchmark. The M0 reference reproduction and source alignment are tracked separately; published counts are not verified pairing counts.

| Source | Availability and terms | Status |
|---|---|---|
| [KITTI](https://www.cvlibs.net/datasets/kitti/) | CC BY-NC-SA 3.0. Keep research images and labels outside public distribution; follow upstream access terms. | Local-data reproduction required. |
| [ReChecked](https://github.com/JonathanKlees/rechecked/tree/1321946698296416d0495999d000dec2deea5e4d) | Pinned upstream commit `1321946698296416d0495999d000dec2deea5e4d`. Validated boxes are not proof of complete review of images absent from the CSV. | Reference correction inputs must remain private to scoring. |
| [Udacity annotations](https://github.com/udacity/self-driving-car/blob/master/annotations/README.md) | README explicitly says intended for educational purposes. CrowdAI set 9,423 frames, Autti set 15,000; different labels and formats. | Actual source and alignment need verification; do not assume Roboflow pairs with either by count. |
| [Roboflow correction](https://public.roboflow.com/object-detection/self-driving-car) | Reports 15,000 images, MIT for updates, 1920×1200 and resized 512×512 exports. Warns duplicate boxes exist. | Download, align and audit changes before replication. The source's educational-use statement needs resolution before redistribution; Roboflow's claim alone is not conclusive for every underlying asset. |
| [RT-DETR](https://huggingface.co/PekingU/rtdetr_r50vd) | Apache-2.0; revision `df939e661d8c52e80608d1ec566561aabd25a4e7`. | Config API and first 1,024 bytes of safetensors returned HTTP 206. Not initially cached. |
| [DINOv2-small](https://huggingface.co/facebook/dinov2-small) | Apache-2.0; revision `ed25f3a31f01632728cabb09d1542f84ab7b0056`. | Config API and first 1,024 bytes of safetensors returned HTTP 206. Not initially cached. |
| [NVIDIA Auto Ontology](https://github.com/NVIDIA/auto-ontology) | Upstream main observed at `d7e553e4c18112479c78b8f846e9929c4b5ed0a3`; this is an observed reference, not a tested integration pin. | Live service/model prerequisites and MCP query untested. |
| Cleanlab / FiftyOne / CVAT | Optional benchmark or export integrations; versions and licenses must be pinned only if actually installed and tested. | Not run. No comparisons claimed. |

Observed machine: Apple M5 Pro, 15 CPUs, 24 GiB unified memory, macOS Darwin 25.6.0 arm64, 576 GiB free. Record actual run device, packages, timing and memory with each experiment; machine inventory is not an inference result.

## Alignment protocol

`python -m pip install pillow` then `python tools/alignment.py ORIGINAL_DIR CORRECTED_DIR --output alignment.json`. Exact is a unique SHA-256 of EXIF-oriented RGB pixels and dimensions. Re-encoded or resized images may produce low-resolution pixel proposals; these are **not accepted matches**. Review source and corrected images visually, check crop/resize geometry, document transformed boxes, and reject ambiguous sequences. Map class definitions independently and manually inspect a stratified sample of changed boxes; a changed box is not automatically a missing label. Report accepted, ambiguous and unmatched counts on both sides after adjudication. The tool's threshold is heuristic and has no measured accuracy; its exhaustive comparison is expensive at full scale and can miss crops or padded images.

No Udacity or Roboflow data has been downloaded or paired in this inventory. No accepted, ambiguous or unmatched dataset counts can be reported yet.

### Endpoint checks and local model staging

On 2026-11-19 the Udacity README's Autti link resolved to `https://s3.amazonaws.com/udacity-sdc/annotations/object-dataset.tar.gz`, HTTP 200, content length 3,550,236,752 bytes. The Roboflow public dataset page redirects to `https://universe.roboflow.com/roboflow-gw7yv/self-driving-car`, which returned HTTP 403 to direct curl; a working export URL was not obtained. No image pairs were compared, so alignment feasibility is unresolved.

Both complete pinned safetensors snapshots were fetched into the local Hugging Face cache, and an isolated Python 3.12 environment with the versions in `recipes/models.json` was installed. CPU inference on the separately licensed Manila image produced 80 detector candidates at confidence ≥ 0.05; initialization took 2.78 seconds and total time 5.27 seconds on this machine. These are unreviewed model outputs, not confirmed omissions.

Correction exchange: `avtriage export --incident INCIDENT --format coco --output JOB/annotations.json` exports portable media and original COCO boxes, with unaccepted proposed suggestions in a separate `suggestions` field. Repeat `--image IMAGE_ID` to export only explicit eligible queue images; default is all eligible queue images, excluding seed, known duplicate group and rejected proposals. JSONL uses per-image records with separate original annotations and suggestions. `avtriage import decisions --input decisions.jsonl` applies valid review records in one transaction, checks stale revisions and idempotency and never edits source annotations. Suggestions remain proposed until an authorized human makes and records a decision; export does not publish revised labels.
