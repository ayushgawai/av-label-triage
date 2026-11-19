import json
import os
import tempfile
from pathlib import Path
import typer
import uvicorn
from .core import (
    import_coco,
    index_predictions,
    create_incident,
    record_review,
    export_replay,
)
from .fixture import demo
from .api import create_app

app = typer.Typer(no_args_is_help=True)
from .audit_cli import register as register_audit

register_audit(app)
from .benchmark_cli import register as register_benchmark

register_benchmark(app)
import_app = typer.Typer(no_args_is_help=True)
app.add_typer(import_app, name="import")


def show(x):
    typer.echo(json.dumps(x, sort_keys=True))


@app.command("demo")
def demo_command(workspace: Path = typer.Option(Path("triage-workspace"))):
    show(demo(workspace))


@import_app.command("coco")
def coco(
    images: Path = typer.Option(...),
    annotations: Path = typer.Option(...),
    policy: Path = typer.Option(...),
    revision: str = typer.Option(...),
    workspace: Path = typer.Option(Path("triage-workspace")),
):
    show({"release_id": import_coco(workspace, images, annotations, policy, revision)})


@app.command("index")
def index(
    release: str = typer.Option(...),
    predictions: Path = typer.Option(None),
    model_revision: str = typer.Option(None),
    device: str = typer.Option("cpu"),
    workspace: Path = typer.Option(Path("triage-workspace")),
):
    if predictions is None:
        from .models import (
            FrozenModels,
            infer_image,
            DETECTOR_REVISION,
            EMBEDDER_REVISION,
        )
        from .core import connect, digest, box_xywh

        model = FrozenModels(device=device)
        with connect(workspace) as db:
            images = list(
                db.execute(
                    "SELECT * FROM images WHERE release_id=? ORDER BY id", (release,)
                )
            )
        if not images:
            raise typer.BadParameter("release has no images")
        records = []
        vectors = []
        for image in images:
            if digest(Path(image["path"]).read_bytes()) != image["sha256"]:
                raise typer.BadParameter("media hash mismatch")
            shard = infer_image(model, image["path"], workspace / "inference-cache")
            for item in shard["proposals"]:
                x1, y1, x2, y2 = item["bbox"]
                vectors.append(
                    (
                        image["id"],
                        box_xywh(
                            [x1, y1, x2 - x1, y2 - y1], image["width"], image["height"]
                        ),
                        float(item["score"]),
                        item["embedding"],
                    )
                )
                records.append(
                    {
                        "image_id": image["id"],
                        "category_id": 1,
                        "bbox": [x1, y1, x2 - x1, y2 - y1],
                        "score": item["score"],
                    }
                )
        predictions = workspace / "inference-cache" / (release + ".predictions.json")
        predictions.write_text(json.dumps(records, sort_keys=True))
        model_revision = DETECTOR_REVISION + "+" + EMBEDDER_REVISION
    elif not model_revision:
        raise typer.BadParameter("--model-revision is required with --predictions")
    result = index_predictions(workspace, release, predictions, model_revision)
    if "vectors" in locals():
        from .core import digest

        embeddings = {
            digest([result["fingerprint"], image_id, bbox, score, "pedestrian"]): vector
            for image_id, bbox, score, vector in vectors
        }
        with connect(workspace) as db:
            ids = {
                row[0]
                for row in db.execute(
                    "SELECT id FROM proposals WHERE index_fingerprint=?",
                    (result["fingerprint"],),
                )
            }
        if set(embeddings) != ids:
            raise RuntimeError("embedding IDs do not match indexed proposals")
        dest = workspace / "bulk" / release / result["fingerprint"] / "embeddings.json"
        fd, temp = tempfile.mkstemp(dir=dest.parent, prefix=".embeddings-")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(embeddings, stream, sort_keys=True, allow_nan=False)
            os.replace(temp, dest)
        finally:
            Path(temp).unlink(missing_ok=True)
    show(result)


@app.command("seed")
def seed(
    release: str = typer.Option(...),
    image: str = typer.Option(...),
    bbox: str = typer.Option(..., help="x1,y1,x2,y2"),
    index_fingerprint: str = typer.Option(...),
    workspace: Path = typer.Option(Path("triage-workspace")),
):
    region = [float(x) for x in bbox.split(",")]
    incident_id = create_incident(workspace, release, image, region, index_fingerprint)
    embeddings = workspace / "bulk" / release / index_fingerprint / "embeddings.json"
    if embeddings.exists():
        from PIL import Image
        from .models import FrozenModels, contextual_crop
        from .core import connect, digest

        with connect(workspace) as db:
            frame = db.execute(
                "SELECT * FROM images WHERE release_id=? AND id=?", (release, image)
            ).fetchone()
        if digest(Path(frame["path"]).read_bytes()) != frame["sha256"]:
            raise typer.BadParameter("media hash mismatch")
        with Image.open(frame["path"]) as source:
            vector = FrozenModels(device="cpu").embed(
                [contextual_crop(source.convert("RGB"), region)]
            )[0]
        dest = (
            workspace
            / "bulk"
            / release
            / index_fingerprint
            / ("seed-" + incident_id + ".json")
        )
        dest.write_text(json.dumps(vector))
    show({"incident_id": incident_id})


@app.command("review")
def review(
    incident: str = typer.Option(...),
    proposal: str = typer.Option(...),
    decision: str = typer.Option(...),
    actor: str = typer.Option(...),
    key: str = typer.Option(...),
    revision: int = typer.Option(...),
    supersedes: str = typer.Option(None),
    region: str = typer.Option(None, help="Final xyxy region, comma separated"),
    workspace: Path = typer.Option(Path("triage-workspace")),
):
    show(
        record_review(
            workspace,
            incident,
            proposal,
            decision,
            "human",
            actor,
            key,
            revision,
            supersedes,
            [float(x) for x in region.split(",")] if region else None,
        )
    )


@app.command("export")
def export(
    incident: str = typer.Option(...),
    format: str = typer.Option("replay"),
    image: list[str] = typer.Option(None, help="Incident queue image ID; repeat for a subset."),
    output: Path = typer.Option(Path("replay.json")),
    workspace: Path = typer.Option(Path("triage-workspace")),
):
    if format == "replay":
        show({"path": str(export_replay(workspace, incident, output))})
        return
    from .exchange import export_job
    show({"path":str(export_job(workspace,incident,output,format, image or None))})


@app.command("serve")
def serve(
    release: str = typer.Option(None),
    workspace: Path = typer.Option(Path("triage-workspace")),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
):
    uvicorn.run(create_app(workspace, release=release), host=host, port=port)


@import_app.command("kitti")
def import_kitti(
    images: Path = typer.Option(...),
    labels: Path = typer.Option(...),
    selection: Path = typer.Option(...),
    partition: str = typer.Option(...),
    policy: Path = typer.Option(...),
    revision: str = typer.Option(...),
    workspace: Path = typer.Option(Path("triage-workspace")),
):
    from .kitti import convert

    data = convert(images, labels, json.loads(selection.read_text()), partition)
    workspace.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=workspace, suffix=".json")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream)
        show(
            {"release_id": import_coco(workspace, images, Path(name), policy, revision)}
        )
    finally:
        Path(name).unlink(missing_ok=True)


@app.command("audit-report")
def audit_report(
    incident: str = typer.Option(...),
    workspace: Path = typer.Option(Path("triage-workspace")),
):
    from .core import connect
    from .audit_api import result

    with connect(workspace) as db:
        design = db.execute(
            "SELECT id FROM audit_designs WHERE incident_id=? ORDER BY created_at DESC LIMIT 1",
            (incident,),
        ).fetchone()
    if not design:
        raise typer.BadParameter("incident has no audit design")
    show(result(workspace, design["id"]))


@import_app.command("decisions")
def import_decisions(
    input: Path = typer.Option(...),
    workspace: Path = typer.Option(Path("triage-workspace")),
):
    from .exchange import import_decisions as load_decisions
    show({"events":load_decisions(workspace,input)})
