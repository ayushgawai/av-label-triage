from pathlib import Path
from html import escape
import json
from .ranking import classify, rank
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .core import connect, record_review, export_replay, digest, create_incident


class Review(BaseModel):
    proposal_id: str
    decision: str
    actor_type: str
    actor_id: str
    idempotency_key: str
    expected_revision: int
    supersedes_id: str | None = None
    region: list[float] | None = None


def incident_data(workspace, incident_id, release=None):
    workspace = Path(workspace)
    with connect(workspace) as db:
        case = db.execute(
            "SELECT * FROM incidents WHERE id=?", (incident_id,)
        ).fetchone()
        if not case or (release and case["release_id"] != release):
            raise HTTPException(404, "incident not found")
        proposals = [
            dict(x)
            for x in db.execute(
                "SELECT * FROM proposals WHERE index_fingerprint=? AND policy_outcome=?",
                (case["index_fingerprint"], "eligible"),
            )
        ]
        for p in proposals:
            p["bbox"] = json.loads(p["bbox_json"])
        annotations = [
            dict(x)
            for x in db.execute(
                "SELECT * FROM source_annotations WHERE release_id=?",
                (case["release_id"],),
            )
        ]
        for a in annotations:
            a["bbox"] = json.loads(a["bbox_json"])
            if a["category"] == "ignore":
                a["category"] = "DontCare"
        images = [
            dict(x)
            for x in db.execute(
                "SELECT * FROM images WHERE release_id=?", (case["release_id"],)
            )
        ]
        metadata = {im["id"]: json.loads(im["metadata_json"]) for im in images}
        for image_id, meta in metadata.items():
            for n, bbox in enumerate(meta.get("ignore_regions", [])):
                annotations.append(
                    {
                        "id": f"ignore:{image_id}:{n}",
                        "image_id": image_id,
                        "bbox": bbox,
                        "category": "DontCare",
                    }
                )
        group = metadata[case["image_id"]].get("duplicate_group")
        excluded = [case["image_id"]] + (
            [
                i
                for i, m in metadata.items()
                if group and m.get("duplicate_group") == group
            ]
        )
        index_dir = workspace / "bulk" / case["release_id"] / case["index_fingerprint"]
        vector_path = index_dir / ("seed-" + incident_id + ".json")
        embeddings_path = index_dir / "embeddings.json"
        method = (
            "fusion"
            if vector_path.exists() and embeddings_path.exists()
            else "confidence"
        )
        seed_vector = (
            json.loads(vector_path.read_text()) if method == "fusion" else [1.0]
        )
        embeddings = (
            json.loads(embeddings_path.read_text()) if method == "fusion" else {}
        )
        queue = rank(
            classify(proposals, annotations),
            seed_vector,
            embeddings,
            method=method,
            excluded_images=excluded,
        )
        return {
            "incident": dict(case),
            "proposals": queue,
            "ranking_method": method,
            "review_events": [
                dict(x)
                for x in db.execute(
                    "SELECT * FROM review_events WHERE incident_id=? ORDER BY rowid",
                    (incident_id,),
                )
            ],
        }


class Seed(BaseModel):
    release_id: str
    image_id: str
    bbox: list[float]
    index_fingerprint: str


def create_app(workspace, release=None):
    workspace = Path(workspace)
    app = FastAPI(title="AV Label Triage")

    @app.get("/api/incidents/{incident_id}")
    def incident(incident_id: str):
        return incident_data(workspace, incident_id, release)

    @app.post("/api/seeds")
    def add_seed(body: Seed):
        from PIL import Image

        try:
            if release and body.release_id != release:
                raise ValueError("release mismatch")
            iid = create_incident(
                workspace,
                body.release_id,
                body.image_id,
                body.bbox,
                body.index_fingerprint,
            )
            index_dir = workspace / "bulk" / body.release_id / body.index_fingerprint
            if (index_dir / "embeddings.json").exists():
                from .models import FrozenModels, contextual_crop

                with connect(workspace) as db:
                    frame = db.execute(
                        "SELECT * FROM images WHERE release_id=? AND id=?",
                        (body.release_id, body.image_id),
                    ).fetchone()
                if digest(Path(frame["path"]).read_bytes()) != frame["sha256"]:
                    raise ValueError("media hash mismatch")
                with Image.open(frame["path"]) as source:
                    vector = FrozenModels(device="cpu").embed(
                        [contextual_crop(source.convert("RGB"), body.bbox)]
                    )[0]
                (index_dir / ("seed-" + iid + ".json")).write_text(json.dumps(vector))
            return {"incident_id": iid}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/images/{release_id}/{image_id}")
    def media(release_id: str, image_id: str):
        with connect(workspace) as db:
            im = db.execute(
                "SELECT path,sha256 FROM images WHERE release_id=? AND id=?",
                (release_id, image_id),
            ).fetchone()
            if not im:
                raise HTTPException(404, "image not found")
            path = Path(im["path"])
            if not path.is_file() or digest(path.read_bytes()) != im["sha256"]:
                raise HTTPException(409, "media missing or hash mismatch")
            return FileResponse(path)

    @app.post("/api/incidents/{incident_id}/reviews")
    def review(incident_id: str, body: Review):
        try:
            return record_review(workspace, incident_id, **body.model_dump())
        except ValueError as e:
            raise HTTPException(409, str(e)) from e

    @app.get("/api/incidents/{incident_id}/replay")
    def replay(incident_id: str):
        try:
            return FileResponse(
                export_replay(
                    workspace,
                    incident_id,
                    workspace / "exports" / f"{incident_id}.json",
                ),
                media_type="application/json",
            )
        except ValueError as e:
            raise HTTPException(404, str(e)) from e

    @app.get("/", response_class=HTMLResponse)
    def home():
        with connect(workspace) as db:
            cases = [
                dict(x)
                for x in db.execute(
                    "SELECT id,image_id FROM incidents WHERE (? IS NULL OR release_id=?) ORDER BY created_at",
                    (release, release),
                )
            ]
        links = "".join(
            f'<li><a href="/viewer/?incident={c["id"]}">{c["id"][:12]} (image {escape(c["image_id"])})</a></li>'
            for c in cases
        )
        return (
            "<h1>AV Label Triage</h1><p>Local review; fixture data is synthetic.</p><ul>"
            + links
            + "</ul>"
        )

    @app.get("/case/{incident_id}", response_class=HTMLResponse)
    def case_page(incident_id: str):
        # IDs are hex digests, so this path is safe to embed in the page.
        if len(incident_id) != 64 or any(
            c not in "0123456789abcdef" for c in incident_id
        ):
            raise HTTPException(404)
        return """<!doctype html><html><head><meta charset="utf-8"><title>Review</title></head><body><h1>Local review</h1><p>Scripted fixture cases are synthetic. Decisions here are recorded with the actor you enter.</p><main id="items"></main><script>
const id=location.pathname.split('/').pop();
async function load(){const r=await fetch('/api/incidents/'+id);if(!r.ok){document.getElementById('items').textContent='Incident not found';return}const data=await r.json();const root=document.getElementById('items');root.replaceChildren();for(const p of data.proposals){const section=document.createElement('section');const h=document.createElement('h2');h.textContent='Image '+p.image_id+' · score '+p.score;section.append(h);const img=document.createElement('img');img.src='/api/images/'+data.incident.release_id+'/'+encodeURIComponent(p.image_id);img.alt='Full frame '+p.image_id;section.append(img);const box=document.createElement('p');box.textContent='Proposed box: '+p.bbox_json;section.append(box);const events=data.review_events.filter(e=>e.proposal_id===p.id);const status=document.createElement('p');status.textContent=events.length?'Last decision: '+events.at(-1).decision:'Unreviewed';section.append(status);for(const decision of ['omission','already_labeled','localization_error','out_of_scope','unresolved']){const b=document.createElement('button');b.textContent=decision;b.onclick=async()=>{const actor=prompt('Reviewer name');if(!actor)return;const result=await fetch('/api/incidents/'+id+'/reviews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({proposal_id:p.id,decision,actor_type:'human',actor_id:actor,idempotency_key:crypto.randomUUID(),expected_revision:events.length,supersedes_id:events.length?events.at(-1).id:null})});if(!result.ok)alert(await result.text());load()};section.append(b)}root.append(section)}}load();</script></body></html>"""

    from .audit_api import register as register_audit

    register_audit(app, workspace)
    from .flash_api import register as register_flash

    register_flash(app, workspace, incident)
    viewer = Path(__file__).resolve().parent / "static"
    if not viewer.exists():
        viewer = Path(__file__).resolve().parent.parent / "space"
    if (viewer / "index.html").is_file():
        app.mount("/viewer", StaticFiles(directory=viewer, html=True), name="viewer")
    return app
