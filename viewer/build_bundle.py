"""Generate a self-contained recorded fixture, never a model or human claim."""

import json
import tempfile
from pathlib import Path
from avtriage.fixture import demo
from avtriage.core import create_incident, export_replay, record_review
from avtriage.api import create_app
from fastapi.testclient import TestClient

out = Path(__file__).parent / "public" / "data"
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as workspace:
    ids = demo(workspace)
    cases = [
        ids["incident_id"],
        create_incident(
            workspace,
            ids["release_id"],
            "1",
            [95, 30, 112, 80],
            ids["index_fingerprint"],
        ),
    ]
    client = TestClient(create_app(workspace))
    from avtriage.audit_api import create_design, inspect, decide

    queue = client.get("/api/incidents/" + cases[0]).json()["proposals"]
    for image_id, decision in [("1", "omission"), ("4", "out_of_scope")]:
        proposal = next(p for p in queue if p["image_id"] == image_id)
        record_review(
            workspace,
            cases[0],
            proposal["id"],
            decision,
            "scripted_fixture",
            "fixture",
            "fixture-" + image_id,
            0,
        )
    audit = create_design(workspace, cases[0], 6, 20261119)
    truth = json.loads((Path(workspace) / "fixture" / "truth.json").read_text())
    for image in inspect(workspace, audit["design_id"])["images"]:
        decide(
            workspace,
            audit["design_id"],
            image["id"],
            "omission" if image["id"] in truth["omitted_image_ids"] else "no_omission",
            "scripted_fixture",
            "fixture",
        )
    for n, case in enumerate(cases):
        path = export_replay(workspace, case, out / f"case-{n}.json")
        replay = json.loads(path.read_text())
        replay["queue"] = client.get("/api/incidents/" + case).json()["proposals"]
        path.write_text(json.dumps(replay, sort_keys=True, indent=2) + "\n")
    (out / "index.json").write_text(
        json.dumps(
            {
                "cases": ["case-0.json", "case-1.json"],
                "provenance": "Synthetic, scripted fixture; recorded proposals, no model inference or human review.",
            }
        )
        + "\n"
    )

# Public photographs retain COCO human annotations except explicitly seeded removals.
source = Path("assets/public/coco")
if (source / "predictions.json").exists():
    import yaml

    with tempfile.TemporaryDirectory() as workspace:
        source_data = json.loads((source / "seeded-original.json").read_text())
        policy = {
            "name": "coco-person-v1",
            "categories": {
                c["name"]: ("pedestrian" if c["name"] == "person" else "other")
                for c in source_data["categories"]
            },
            "prediction_categories": {"1": "pedestrian"},
        }
        policy_path = Path(workspace) / "policy.yml"
        policy_path.write_text(yaml.safe_dump(policy))
        from avtriage.core import import_coco, index_predictions

        release = import_coco(
            workspace,
            source,
            source / "seeded-original.json",
            policy_path,
            "coco-public-seeded-v1",
        )
        idx = index_predictions(
            workspace,
            release,
            source / "predictions.json",
            "rtdetr-r50-df939e661d8c52e80608d1ec566561aabd25a4e7",
        )
        client = TestClient(create_app(workspace))
        credits = {
            "142472": [
                "Elliott Brown",
                "https://www.flickr.com/photos/ell-r-brown/7871818696/",
            ],
            "184324": [
                "Serge Melki",
                "https://www.flickr.com/photos/sergemelki/3364389746/",
            ],
            "210273": ["Tauno Tõhk", "https://www.flickr.com/photos/toehk/5336041838/"],
            "301376": [
                "Chad Kainz",
                "https://www.flickr.com/photos/smaedli/2718408461/",
            ],
            "309391": [
                "Ian Sane",
                "https://www.flickr.com/photos/31246066@N04/5329327710/",
            ],
        }
        for n, seed in enumerate(
            json.loads((source / "seed-manifest.json").read_text())
        ):
            x, y, w, h = seed["bbox"]
            incident = create_incident(
                workspace,
                release,
                str(seed["image_id"]),
                [x, y, x + w, y + h],
                idx["fingerprint"],
            )
            create_design(workspace, incident, 3, 20261119)
            path = export_replay(workspace, incident, out / f"photo-{n}.json")
            replay = json.loads(path.read_text())
            recorded = json.loads((source / "recorded-replays.json").read_text())[
                "replays"
            ][n]
            queue = []
            for candidate in recorded["queue"]:
                matches = [
                    p
                    for p in replay["proposals"]
                    if p["image_id"] == candidate["image_id"]
                    and abs(p["score"] - candidate["score"]) < 1e-8
                    and max(abs(a - b) for a, b in zip(p["bbox"], candidate["bbox"]))
                    < 1e-7
                ]
                if len(matches) != 1:
                    raise ValueError("recorded candidate missing or ambiguous")
                queue.append({**candidate, "id": matches[0]["id"]})
            replay["queue"] = queue
            replay["ranking_method"] = "fusion"
            for image in replay["images"]:
                image["metadata"]["attribution"] = {
                    "creator": credits[image["id"]][0],
                    "source": credits[image["id"]][1],
                    "license": "https://creativecommons.org/licenses/by/2.0/",
                }
            replay["provenance"] = (
                "COCO 2017 human annotations with deliberate seeded omissions; RT-DETR recorded inference. No independent human pilot."
            )
            path.write_text(json.dumps(replay, sort_keys=True, indent=2) + "\n")
