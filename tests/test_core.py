import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from avtriage.core import (
    connect,
    index_predictions,
    record_review,
    export_replay,
    digest,
)
from avtriage.fixture import demo
from avtriage.api import create_app


def test_offline_replay_review_and_immutable_index(tmp_path):
    ids = demo(tmp_path)
    incident = ids["incident_id"]
    fixture = tmp_path / "fixture"
    source = json.loads((fixture / "predictions.json").read_text())
    source.reverse()
    reordered = tmp_path / "reordered.json"
    reordered.write_text(json.dumps(source))
    assert (
        index_predictions(
            tmp_path, ids["release_id"], reordered, "scripted-fixture-v1"
        )["fingerprint"]
        == ids["index_fingerprint"]
    )
    with connect(tmp_path) as db:
        proposal = db.execute(
            "SELECT id FROM proposals WHERE index_fingerprint=? AND image_id=?",
            (ids["index_fingerprint"], "1"),
        ).fetchone()[0]
    args = (
        tmp_path,
        incident,
        proposal,
        "omission",
        "scripted_fixture",
        "fixture",
        "key",
        0,
    )
    first = record_review(*args)
    assert record_review(*args)["id"] == first["id"]
    with pytest.raises(ValueError, match="stale"):
        record_review(
            tmp_path,
            incident,
            proposal,
            "unresolved",
            "scripted_fixture",
            "fixture",
            "other",
            0,
        )
    second = record_review(
        tmp_path,
        incident,
        proposal,
        "unresolved",
        "scripted_fixture",
        "fixture",
        "next",
        1,
        first["id"],
    )
    assert second["supersedes_id"] == first["id"]
    out = export_replay(tmp_path, incident, tmp_path / "export" / "case.json")
    payload = json.loads(out.read_text())
    assert payload["incident"]["id"] == incident and len(payload["review_events"]) == 2
    for image in payload["images"]:
        assert digest((out.parent / image["path"]).read_bytes()) == image["sha256"]
    response = TestClient(create_app(tmp_path)).get("/api/incidents/" + incident)
    assert response.status_code == 200
    body = response.json()
    assert [e["id"] for e in body["review_events"]] == [first["id"], second["id"]]
    assert not {"0", "7"} & {p["image_id"] for p in body["proposals"]}


def test_concurrent_review_conflict_and_index_staging(tmp_path):
    ids = demo(tmp_path)
    with connect(tmp_path) as db:
        proposal = db.execute(
            "SELECT id FROM proposals WHERE image_id=?", ("1",)
        ).fetchone()[0]

    def write(key):
        try:
            return record_review(
                tmp_path, ids["incident_id"], proposal, "omission", "human", key, key, 0
            )["id"]
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["a", "b"]))
    assert sum(x is not None for x in results) == 1
    # An interrupted staging file cannot be mistaken for a completed index.
    f = (
        tmp_path
        / "bulk"
        / ids["release_id"]
        / ids["index_fingerprint"]
        / ".index-interrupted"
    )
    f.write_text("partial")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: index_predictions(
                    tmp_path,
                    ids["release_id"],
                    tmp_path / "fixture" / "predictions.json",
                    "scripted-fixture-v1",
                ),
                range(2),
            )
        )
    assert all(r["fingerprint"] == ids["index_fingerprint"] for r in results)


def test_truth_does_not_enter_release_or_replay(tmp_path):
    ids = demo(tmp_path)
    out = export_replay(tmp_path, ids["incident_id"], tmp_path / "replay.json")
    replay = json.loads(out.read_text())
    assert all("fixture_case" not in image["metadata"] for image in replay["images"])
    assert "omitted_image_ids" not in out.read_text()
    assert json.loads((tmp_path / "fixture" / "truth.json").read_text())[
        "omitted_image_ids"
    ]


def test_api_fusion_changes_with_seed_vector(tmp_path):
    ids = demo(tmp_path)
    index_dir = tmp_path / "bulk" / ids["release_id"] / ids["index_fingerprint"]
    with connect(tmp_path) as db:
        proposals = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM proposals WHERE image_id IN ('1','4') ORDER BY image_id"
            )
        ]
    (index_dir / "embeddings.json").write_text(
        json.dumps({proposals[0]["id"]: [1, 0], proposals[1]["id"]: [0, 1]})
    )
    vector = index_dir / ("seed-" + ids["incident_id"] + ".json")
    client = TestClient(create_app(tmp_path))
    vector.write_text("[1,0]")
    first = client.get("/api/incidents/" + ids["incident_id"]).json()
    vector.write_text("[0,1]")
    second = client.get("/api/incidents/" + ids["incident_id"]).json()
    assert first["ranking_method"] == second["ranking_method"] == "fusion"
    assert [p["similarity_rank"] for p in first["proposals"]] != [p["similarity_rank"] for p in second["proposals"]]
