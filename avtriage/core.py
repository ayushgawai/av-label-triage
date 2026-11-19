from __future__ import annotations
import hashlib
import json
import math
import os
import sqlite3
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from PIL import Image


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(
        value if isinstance(value, bytes) else canonical(value).encode()
    ).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def connect(workspace):
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(workspace / "triage.sqlite", timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS policies(id TEXT PRIMARY KEY, body_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS releases(id TEXT PRIMARY KEY, dataset_revision TEXT NOT NULL, policy_id TEXT NOT NULL REFERENCES policies(id), manifest_json TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS images(release_id TEXT NOT NULL REFERENCES releases(id), id TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, metadata_json TEXT NOT NULL, PRIMARY KEY(release_id,id));
    CREATE TABLE IF NOT EXISTS source_annotations(release_id TEXT NOT NULL, id TEXT NOT NULL, image_id TEXT NOT NULL, category TEXT NOT NULL, bbox_json TEXT NOT NULL, PRIMARY KEY(release_id,id), FOREIGN KEY(release_id,image_id) REFERENCES images(release_id,id));
    CREATE TABLE IF NOT EXISTS indices(fingerprint TEXT PRIMARY KEY, release_id TEXT NOT NULL REFERENCES releases(id), model_revision TEXT NOT NULL, predictions_sha256 TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS proposals(release_id TEXT NOT NULL, index_fingerprint TEXT NOT NULL REFERENCES indices(fingerprint), id TEXT NOT NULL, image_id TEXT NOT NULL, bbox_json TEXT NOT NULL, score REAL NOT NULL, category TEXT NOT NULL, model_revision TEXT NOT NULL, policy_outcome TEXT NOT NULL, reason_codes_json TEXT NOT NULL, PRIMARY KEY(index_fingerprint,id), FOREIGN KEY(release_id,image_id) REFERENCES images(release_id,id));
    CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY, release_id TEXT NOT NULL REFERENCES releases(id), image_id TEXT NOT NULL, bbox_json TEXT NOT NULL, policy_id TEXT NOT NULL REFERENCES policies(id), index_fingerprint TEXT NOT NULL REFERENCES indices(fingerprint), created_at TEXT NOT NULL, FOREIGN KEY(release_id,image_id) REFERENCES images(release_id,id));
    CREATE TABLE IF NOT EXISTS review_events(id TEXT PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(id), proposal_id TEXT NOT NULL, image_id TEXT NOT NULL, region_json TEXT NOT NULL, policy_id TEXT NOT NULL, decision TEXT NOT NULL, actor_type TEXT NOT NULL, actor_id TEXT NOT NULL, supersedes_id TEXT REFERENCES review_events(id), expected_revision INTEGER NOT NULL, idempotency_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit_designs(id TEXT PRIMARY KEY, release_id TEXT NOT NULL, incident_id TEXT NOT NULL, manifest_hash TEXT NOT NULL, seed INTEGER NOT NULL, population_json TEXT NOT NULL, strata_json TEXT NOT NULL, sample_size INTEGER NOT NULL, policy_id TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit_draws(design_id TEXT NOT NULL REFERENCES audit_designs(id), image_id TEXT NOT NULL, stratum TEXT NOT NULL, inclusion_probability REAL NOT NULL, PRIMARY KEY(design_id,image_id));
    CREATE TABLE IF NOT EXISTS audit_decisions(id TEXT PRIMARY KEY, design_id TEXT NOT NULL REFERENCES audit_designs(id), image_id TEXT NOT NULL, decision TEXT NOT NULL, actor_type TEXT NOT NULL, actor_id TEXT NOT NULL, supersedes_id TEXT REFERENCES audit_decisions(id), created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS run_manifests(id TEXT PRIMARY KEY, release_id TEXT NOT NULL, incident_id TEXT NOT NULL, kind TEXT NOT NULL, config_json TEXT NOT NULL, artifacts_json TEXT NOT NULL, created_at TEXT NOT NULL);
    PRAGMA user_version=1;
    """)
    return db


def box_xywh(box, width, height):
    if len(box) != 4 or not all(
        isinstance(x, (float, int)) and math.isfinite(x) for x in box
    ):
        raise ValueError("invalid box")
    x, y, w, h = box
    if w <= 0 or h <= 0:
        raise ValueError("nonpositive box")
    result = [
        max(0.0, min(float(width), float(x))),
        max(0.0, min(float(height), float(y))),
        max(0.0, min(float(width), float(x + w))),
        max(0.0, min(float(height), float(y + h))),
    ]
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError("box outside image")
    return result


def import_coco(workspace, images, annotations, policy, revision):
    images, annotations, policy = (
        Path(images).resolve(),
        Path(annotations),
        Path(policy),
    )
    data = json.loads(annotations.read_text())
    rules = yaml.safe_load(policy.read_text())
    if (
        not revision
        or not isinstance(rules, dict)
        or not isinstance(rules.get("categories"), dict)
    ):
        raise ValueError("revision and policy categories required")
    categories = {str(c["id"]): c["name"] for c in data["categories"]}
    if len(categories) != len(data["categories"]):
        raise ValueError("duplicate category")
    normalized_images = []
    for im in data["images"]:
        path = (images / im["file_name"]).resolve()
        if not path.is_relative_to(images) or not path.is_file():
            raise ValueError("invalid image path")
        with Image.open(path) as decoded:
            if decoded.getexif().get(274, 1) != 1:
                raise ValueError(
                    "EXIF-oriented images must be normalized with their annotations before import"
                )
            if decoded.size != (im["width"], im["height"]):
                raise ValueError("image dimensions mismatch")
        with Image.open(path) as decoded:
            decoded.verify()
        normalized_images.append(
            dict(
                id=str(im["id"]),
                file_name=im["file_name"],
                sha256=digest(path.read_bytes()),
                width=im["width"],
                height=im["height"],
                metadata=im.get("metadata", {}),
            )
        )
    by_id = {x["id"]: x for x in normalized_images}
    if len(by_id) != len(normalized_images):
        raise ValueError("duplicate image ID")
    anns = []
    for ann in data["annotations"]:
        im = by_id[str(ann["image_id"])]
        category = categories[str(ann["category_id"])]
        mapped = rules["categories"].get(category)
        if mapped is None:
            raise ValueError(f"unmapped category: {category}")
        anns.append(
            dict(
                id=str(ann["id"]),
                image_id=im["id"],
                category=mapped,
                bbox=box_xywh(ann["bbox"], im["width"], im["height"]),
            )
        )
    if len({a["id"] for a in anns}) != len(anns):
        raise ValueError("duplicate annotation ID")
    manifest = dict(
        revision=revision,
        policy=rules,
        images=sorted(normalized_images, key=lambda x: x["id"]),
        annotations=sorted(anns, key=lambda x: x["id"]),
    )
    release = digest(manifest)
    policy_id = digest(rules)
    with connect(workspace) as db:
        db.execute(
            "INSERT OR IGNORE INTO policies VALUES (?,?)", (policy_id, canonical(rules))
        )
        db.execute(
            "INSERT OR IGNORE INTO releases VALUES (?,?,?,?,?)",
            (release, revision, policy_id, canonical(manifest), now()),
        )
        for im in normalized_images:
            media = Path(workspace) / "media" / im["sha256"]
            media.parent.mkdir(parents=True, exist_ok=True)
            if not media.exists():
                fd, tmp = tempfile.mkstemp(dir=media.parent, prefix=".media-")
                os.close(fd)
                try:
                    shutil.copyfile(images / im["file_name"], tmp)
                    if digest(Path(tmp).read_bytes()) != im["sha256"]:
                        raise ValueError("image changed during import")
                    os.replace(tmp, media)
                finally:
                    Path(tmp).unlink(missing_ok=True)
            elif digest(media.read_bytes()) != im["sha256"]:
                raise ValueError("stored image hash mismatch")
            db.execute(
                "INSERT OR IGNORE INTO images VALUES (?,?,?,?,?,?,?)",
                (
                    release,
                    im["id"],
                    str(media.resolve()),
                    im["sha256"],
                    im["width"],
                    im["height"],
                    canonical(im["metadata"]),
                ),
            )
        for a in anns:
            db.execute(
                "INSERT OR IGNORE INTO source_annotations VALUES (?,?,?,?,?)",
                (release, a["id"], a["image_id"], a["category"], canonical(a["bbox"])),
            )
    return release


def index_predictions(workspace, release_id, predictions, model_revision):
    raw = Path(predictions).read_bytes()
    data = json.loads(raw)
    if not isinstance(data, list) or not model_revision:
        raise ValueError("predictions list and model revision required")
    with connect(workspace) as db:
        release = db.execute(
            "SELECT * FROM releases WHERE id=?", (release_id,)
        ).fetchone()
        if not release:
            raise ValueError("release not found")
        manifest = json.loads(release["manifest_json"])
        # Prediction category IDs correspond to the source COCO categories captured during import.
        categories = manifest["policy"].get("prediction_categories", {})
        images = {
            r["id"]: r
            for r in db.execute(
                "SELECT * FROM images WHERE release_id=?", (release_id,)
            )
        }
        normalized = []
        for item in data:
            im = images[str(item["image_id"])]
            score = item["score"]
            if (
                not isinstance(score, (int, float))
                or not math.isfinite(score)
                or not 0 <= score <= 1
            ):
                raise ValueError("invalid score")
            category = categories.get(str(item["category_id"]))
            if category is None:
                raise ValueError("unmapped prediction category")
            normalized.append(
                {
                    "image_id": im["id"],
                    "bbox": box_xywh(item["bbox"], im["width"], im["height"]),
                    "score": float(score),
                    "category": category,
                }
            )
        normalized.sort(key=canonical)
        fingerprint = digest(
            [
                release_id,
                normalized,
                model_revision,
                release["policy_id"],
                "predictions-v1",
            ]
        )
        dest = Path(workspace) / "bulk" / release_id / fingerprint / "proposals.parquet"
        if (
            db.execute(
                "SELECT 1 FROM indices WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            and dest.is_file()
        ):
            return {
                "fingerprint": fingerprint,
                "count": len(normalized),
                "parquet": str(dest),
            }
        rows = []
        for item in normalized:
            bbox = item["bbox"]
            category = item["category"]
            score = item["score"]
            pid = digest([fingerprint, item["image_id"], bbox, score, category])
            outcome = "eligible" if category == "pedestrian" else "out_of_scope"
            rows.append(
                dict(
                    release_id=release_id,
                    proposal_id=pid,
                    image_id=item["image_id"],
                    x1=bbox[0],
                    y1=bbox[1],
                    x2=bbox[2],
                    y2=bbox[3],
                    score=score,
                    category=category,
                    model_revision=model_revision,
                    policy_outcome=outcome,
                    reason_codes_json=canonical(
                        [] if outcome == "eligible" else ["category_out_of_scope"]
                    ),
                )
            )
        if len({r["proposal_id"] for r in rows}) != len(rows):
            raise ValueError("duplicate predictions")
        rows.sort(key=lambda r: (r["image_id"], r["proposal_id"]))
        dest = Path(workspace) / "bulk" / release_id / fingerprint / "proposals.parquet"
        dest.parent.mkdir(parents=True, exist_ok=True)
        schema = pa.schema(
            [
                (
                    n,
                    (
                        pa.float64()
                        if n in ("x1", "y1", "x2", "y2", "score")
                        else pa.string()
                    ),
                )
                for n in (
                    "release_id",
                    "proposal_id",
                    "image_id",
                    "x1",
                    "y1",
                    "x2",
                    "y2",
                    "score",
                    "category",
                    "model_revision",
                    "policy_outcome",
                    "reason_codes_json",
                )
            ]
        )
        fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".index-")
        os.close(fd)
        try:
            pq.write_table(pa.Table.from_pylist(rows, schema=schema), tmp)
            os.replace(tmp, dest)
        finally:
            Path(tmp).unlink(missing_ok=True)
        db.execute(
            "INSERT OR IGNORE INTO indices VALUES (?,?,?,?,?)",
            (fingerprint, release_id, model_revision, digest(raw), now()),
        )
        for r in rows:
            db.execute(
                "INSERT OR IGNORE INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    release_id,
                    fingerprint,
                    r["proposal_id"],
                    r["image_id"],
                    canonical([r["x1"], r["y1"], r["x2"], r["y2"]]),
                    r["score"],
                    r["category"],
                    model_revision,
                    r["policy_outcome"],
                    r["reason_codes_json"],
                ),
            )
    return {"fingerprint": fingerprint, "count": len(rows), "parquet": str(dest)}


def create_incident(workspace, release_id, image_id, bbox, index_fingerprint):
    with connect(workspace) as db:
        im = db.execute(
            "SELECT * FROM images WHERE release_id=? AND id=?",
            (release_id, str(image_id)),
        ).fetchone()
        index = db.execute(
            "SELECT * FROM indices WHERE fingerprint=? AND release_id=?",
            (index_fingerprint, release_id),
        ).fetchone()
        if not im or not index:
            raise ValueError("image or index not found")
        if len(bbox) != 4:
            raise ValueError("invalid box")
        bbox = box_xywh(
            [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]],
            im["width"],
            im["height"],
        )
        policy = db.execute(
            "SELECT policy_id FROM releases WHERE id=?", (release_id,)
        ).fetchone()[0]
        iid = digest([release_id, str(image_id), bbox, index_fingerprint, policy])
        db.execute(
            "INSERT OR IGNORE INTO incidents VALUES (?,?,?,?,?,?,?)",
            (
                iid,
                release_id,
                str(image_id),
                canonical(bbox),
                policy,
                index_fingerprint,
                now(),
            ),
        )
        return iid


def record_review(
    workspace,
    incident_id,
    proposal_id,
    decision,
    actor_type,
    actor_id,
    idempotency_key,
    expected_revision,
    supersedes_id=None,
    region=None,
    _db=None,
):
    if (
        decision
        not in {
            "omission",
            "already_labeled",
            "localization_error",
            "out_of_scope",
            "unresolved",
        }
        or actor_type not in {"human", "scripted_fixture", "visitor"}
        or not actor_id
        or not idempotency_key
    ):
        raise ValueError("invalid review")
    own_connection = _db is None
    db = connect(workspace) if own_connection else _db
    try:
        if own_connection: db.execute("BEGIN IMMEDIATE")
        old = db.execute(
            "SELECT * FROM review_events WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone()
        if old:
            if region is not None and json.loads(old["region_json"]) != region:
                raise ValueError("idempotency key reused with different region")
            if (
                old["incident_id"],
                old["proposal_id"],
                old["decision"],
                old["actor_type"],
                old["actor_id"],
                old["expected_revision"],
                old["supersedes_id"],
            ) != (
                incident_id,
                proposal_id,
                decision,
                actor_type,
                actor_id,
                expected_revision,
                supersedes_id,
            ):
                raise ValueError("idempotency key reused")
            if own_connection: db.commit()
            return dict(old)
        incident = db.execute(
            "SELECT * FROM incidents WHERE id=?", (incident_id,)
        ).fetchone()
        if not incident:
            raise ValueError("incident not found")
        proposal = db.execute(
            "SELECT * FROM proposals WHERE index_fingerprint=? AND id=?",
            (incident["index_fingerprint"], proposal_id),
        ).fetchone()
        if not proposal:
            raise ValueError("proposal not found in incident index")
        if region is None:
            region_json = proposal["bbox_json"]
        else:
            image = db.execute(
                "SELECT width,height FROM images WHERE release_id=? AND id=?",
                (incident["release_id"], proposal["image_id"]),
            ).fetchone()
            if len(region) != 4:
                raise ValueError("invalid review region")
            region_json = canonical(
                box_xywh(
                    [
                        region[0],
                        region[1],
                        region[2] - region[0],
                        region[3] - region[1],
                    ],
                    image["width"],
                    image["height"],
                )
            )
        events = db.execute(
            "SELECT * FROM review_events WHERE incident_id=? AND proposal_id=? ORDER BY rowid",
            (incident_id, proposal_id),
        ).fetchall()
        if len(events) != expected_revision:
            raise ValueError("stale revision")
        if (events[-1]["id"] if events else None) != supersedes_id:
            raise ValueError("supersedes must be latest event")
        eid = digest(
            [
                idempotency_key,
                incident_id,
                proposal_id,
                decision,
                actor_type,
                actor_id,
                expected_revision,
                supersedes_id,
            ]
        )
        db.execute(
            "INSERT INTO review_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                eid,
                incident_id,
                proposal_id,
                proposal["image_id"],
                region_json,
                incident["policy_id"],
                decision,
                actor_type,
                actor_id,
                supersedes_id,
                expected_revision,
                idempotency_key,
                now(),
            ),
        )
        event = dict(
            db.execute("SELECT * FROM review_events WHERE id=?", (eid,)).fetchone()
        )
        if own_connection: db.commit()
        return event
    finally:
        if own_connection: db.close()


def export_replay(workspace, incident_id, output):
    with connect(workspace) as db:
        incident = db.execute(
            "SELECT * FROM incidents WHERE id=?", (incident_id,)
        ).fetchone()
        if not incident:
            raise ValueError("incident not found")
        release = dict(
            db.execute(
                "SELECT * FROM releases WHERE id=?", (incident["release_id"],)
            ).fetchone()
        )
        policy = dict(
            db.execute(
                "SELECT * FROM policies WHERE id=?", (incident["policy_id"],)
            ).fetchone()
        )

        def rows(query, args):
            return [dict(r) for r in db.execute(query, args)]

        images = rows(
            "SELECT * FROM images WHERE release_id=? ORDER BY id", (release["id"],)
        )
        from .api import incident_data

        queue_data = incident_data(workspace, incident_id)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        media_dir = output.parent / (output.stem + "_media")
        media_dir.mkdir(exist_ok=True)
        for im in images:
            source = Path(im["path"])
            if digest(source.read_bytes()) != im["sha256"]:
                raise ValueError("stored image hash mismatch")
            dest = media_dir / im["sha256"]
            shutil.copyfile(source, dest)
            im["path"] = f'{media_dir.name}/{im["sha256"]}'
        design = db.execute(
            "SELECT * FROM audit_designs WHERE incident_id=? ORDER BY created_at DESC LIMIT 1",
            (incident_id,),
        ).fetchone()
        audit = None
        if design:
            from .audit_api import inspect as inspect_audit, result as audit_result

            audit = {
                "design": dict(design),
                "blind": inspect_audit(workspace, design["id"]),
                "result": audit_result(workspace, design["id"]),
            }
        result = {
            "schema_version": 1,
            "queue": queue_data["proposals"],
            "ranking_method": queue_data["ranking_method"],
            "release": release,
            "policy": policy,
            "images": images,
            "annotations": rows(
                "SELECT * FROM source_annotations WHERE release_id=? ORDER BY id",
                (release["id"],),
            ),
            "proposals": rows(
                "SELECT * FROM proposals WHERE index_fingerprint=? ORDER BY image_id,id",
                (incident["index_fingerprint"],),
            ),
            "incident": dict(incident),
            "review_events": rows(
                "SELECT * FROM review_events WHERE incident_id=? ORDER BY created_at,id",
                (incident_id,),
            ),
            "audit": audit,
            "run_manifest": dict(
                db.execute(
                    "SELECT * FROM indices WHERE fingerprint=?",
                    (incident["index_fingerprint"],),
                ).fetchone()
            ),
        }
        for obj in [
            result["release"],
            result["policy"],
            result["incident"],
            *result["images"],
            *result["annotations"],
            *result["proposals"],
            *result["review_events"],
        ]:
            for key in list(obj):
                if key.endswith("_json"):
                    obj[key[:-5]] = json.loads(obj.pop(key))
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp = output.with_suffix(output.suffix + ".tmp")
        tmp.write_text(canonical(result) + "\n")
        os.replace(tmp, output)
        return output
