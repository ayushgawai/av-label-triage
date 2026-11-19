# KITTI / ReChecked reference comparison

The reference cohort is the 1,497 IDs in ReChecked's validation split, selected without using correction rows. It is not a fully adjudicated population: absence from the correction CSV is not evidence of no error. Its 3,078 reference rows cover 761 filenames. A reference-derived overlooked box is a **known reference omission**, not a human-confirmed negative; an unmatched model candidate remains awaiting inspection. Never expose this CSV to mining, ranking, or blinded audits.

Sources: [KITTI](https://www.cvlibs.net/datasets/kitti/), [official detection benchmark](https://www.cvlibs.net/datasets/kitti/eval_object.php), [pinned ReChecked](https://github.com/JonathanKlees/rechecked/tree/1321946698296416d0495999d000dec2deea5e4d), [upstream comparison](https://github.com/JonathanKlees/rechecked/blob/1321946698296416d0495999d000dec2deea5e4d/compare_annotations.py). KITTI states CC BY-NC-SA 3.0; consult its current terms before use or redistribution. ReChecked code is MIT; the terms and provenance of data are separate. No third-party data is bundled here.

## Inputs and reproducibility

Store inputs outside the project and keep references private from the miner. Acquire KITTI training labels from the official archive and check SHA-256 `4efc76220d867e1c31bb980bbf8cbc02599f02a9cb4350effa98dbb04aaed880`. Pin ReChecked commit `1321946698296416d0495999d000dec2deea5e4d`; `data/validated_gt.csv` SHA-256 is `4a029e322ccacd281cf3158987f8cada9fb1e52fad9b605412f75681a3a8583f` and `data/train_val_split.json` SHA-256 is `9bbb95193c9f4f7ce2aa35e455c40b223b70702667844598538cee2abe470dd7`.

```sh
python3 tools/reference_compare.py --labels /path/to/kitti/training/label_2 \
  --reference /private/rechecked/data/validated_gt.csv \
  --split /private/rechecked/data/train_val_split.json
python3 -m unittest discover -s tests -p 'test_reference*' -v
```

The frozen configuration uses reference probability >= 0.8, height >= 40 px and excludes DontCare intersection / candidate area >= 0.5. Both original and corrected boxes are size and DontCare filtered. Only original `Pedestrian` boxes are matched. Coordinates are xyxy pixels; intersection and area use continuous coordinates. The upstream procedure traverses validated rows in CSV order; for each, it greedily consumes the highest-IoU unused original box only if IoU >= 0.5. A zero best IoU is overlooked, an overlap below 0.5 is misfitting. It is not maximum matching and is order-sensitive. This script reproduces the 12 settings in upstream `compile_table.py` (probability 0.5/0.8, height 0/25/40, DontCare on/off). The benchmark settings are not a universal labeling policy.

To run the authors' implementation independently, create a Python 3.12 environment with their pinned torch, torchvision, numpy and pandas versions; run `process_kitti.py` from the checkout, providing the KITTI root, then `compile_table.py` with that environment's `python` on PATH. Generated CSVs and source data must stay private.

## Reproduction result (2026-11-19)

On macOS arm64, Python 3.12, torch 2.6.0, torchvision 0.21.0, NumPy 2.2.4 and pandas 2.2.3, the pinned upstream `process_kitti.py` loaded all 7,481 original label files and `compile_table.py` produced the following counts. The independent script above agrees on all 12 overlooked/misfitting pairs. Matched counts were not printed by upstream. These are box counts, not image prevalence or detector performance.

| DontCare filtered | Height | p >= 0.5 overlooked / misfitting | p >= 0.8 overlooked / misfitting |
|---|---:|---:|---:|
| No | 0 | 683 / 179 | 272 / 115 |
| No | 25 | 454 / 162 | 218 / 112 |
| No | 40 | 157 / 118 | 83 / 89 |
| Yes | 0 | 341 / 173 | 121 / 112 |
| Yes | 25 | 228 / 156 | 97 / 109 |
| Yes | 40 | 91 / 114 | **42 / 87** |

## Held-out subset, fixed before inspecting its reference outcomes

Order all 1,497 validation IDs by SHA-256 of UTF-8 `avtriage-m0-2026-11-19:<id>` and take the first 160. Derive original drive IDs with the object development kit's `train_rand.txt` permutation and `train_mapping.txt`. Order their 58 drives by SHA-256 of `avtriage-drive-2026-11-19:<drive>`; the first 14 drives are development (27 selected frames), the remaining 44 evaluation (133 selected frames). The local manifest is `/tmp/avtriage-reference/grouped-selection.json`. Official image members are downloaded by HTTP range from `https://s3.eu-central-1.amazonaws.com/avg-kitti/data_object_image_2.zip` to `/tmp/avtriage-reference/kitti/training/image_2`; these are not a public bundle.

The official object development kit is currently behind KITTI login. Mapping files were retrieved from the [devkit mirror](https://github.com/bostondiditeam/kitti/tree/master/resources/devkit_object/mapping); their SHA-256 values are `ca9a80524adbfbebc3179987e70a8dab1488a88ba368e77715d561c901196a54` (mapping) and `0976b8b4f876f538010a9690249b60c0766d852e23acd5e07b4c3e0bd70f305f` (permutation). The mapping reproduces the devkit's documented image 000000 example, but byte-for-byte comparison with an authenticated official download remains outstanding.

Before inspecting any development corrections, choose up to three eligible known dev omissions ordered by the same image hash, at most one per drive. If none exist in the 27 selected dev images, extend to other validation IDs on those dev drives in the same hash order. Exclude all seed images and their drives from discovery credit. Do not inspect evaluation corrections until queues and configuration are frozen. Record exact selected seeds and any fallback use separately; no seed has yet been selected. Real human confirmation and audit remain outstanding.

After freezing the above rule, one seed was found in the selected development frames: `000736`, drive `2011_09_26_drive_0095_sync`; no fallback was used. Its private coordinates and correction row are at `/tmp/avtriage-reference/dev-seeds-private.json`. The seed group is development-only. All 160 image files were extracted and original-only development/evaluation COCO files were generated locally using `tools/reference_kitti.py` and `recipes/kitti-policy.yml`. The adapter preserves DontCare and cyclist classes, clips source boxes to the verified image dimensions, and includes mapped drive IDs. Upstream comparisons intentionally use raw original coordinates and do not use this COCO adapter.

The independent comparator uses Python float64 arithmetic, whereas upstream uses torch float32. All aggregate counts agree on the pinned inputs; threshold-boundary behavior on other inputs is not guaranteed identical. The original greedy comparison is row-order-sensitive even though release ingestion and ranking use stable IDs.

For a fresh private cache, `python tools/reference_fetch.py /absolute/path/outside/repo --images` downloads the original labels, checks their SHA-256, checks out the pinned ReChecked revision and validates both CSV/split hashes. Install `remotezip` separately for image HTTP ranges. The fixed selection manifest is `recipes/kitti-image-selection.json`; image content remains local and source licensing applies. No auth credentials are required by this fetch script, although official source availability can change.

With the data and frozen outputs under the cache root, `AVTRIAGE_REFERENCE_ROOT=/path/to/cache avtriage benchmark --config /absolute/path/to/recipes/kitti-rechecked.yml` runs the same package scorer used to generate the checked-in aggregate artifact, including secondary tile image reach and conditional drive bootstrap. Frozen private queue files are produced by the model pipeline; fetching source data alone does not generate them.

Recreate the private seed without inspecting held-out corrections: `python -m tools.reference_seed --labels "$AVTRIAGE_REFERENCE_ROOT/kitti/training/label_2" --reference "$AVTRIAGE_REFERENCE_ROOT/rechecked/data/validated_gt.csv" --selection recipes/kitti-image-selection.json > "$AVTRIAGE_REFERENCE_ROOT/dev-seeds-private.json"`. This reproduces the one selected seed. If no seed exists in the frozen development sample, this tool stops and the predeclared dev-drive fallback must be implemented from the mapping; it does not automatically inspect evaluation images.
