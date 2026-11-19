import json
from pathlib import Path
from PIL import Image, ImageDraw
from .core import import_coco, index_predictions, create_incident


def generate(root):
    root = Path(root)
    images = root / "images"
    images.mkdir(parents=True, exist_ok=True)
    # Synthetic geometry is fixed: no external images, randomness, or human labels.
    people = [
        (20, 35, 18, 48),
        (95, 30, 17, 50),
        (155, 40, 14, 40),
        (220, 32, 16, 48),
        (60, 33, 17, 49),
        (100, 32, 16, 50),
        (200, 35, 15, 47),
        (20, 35, 18, 48),
        (130, 38, 16, 42),
    ]
    for i, person in enumerate(people):
        im = Image.new("RGB", (320, 120), "#dbe8ed")
        d = ImageDraw.Draw(im)
        d.rectangle((0, 85, 320, 120), fill="#777777")
        x, y, w, h = person
        if i == 4:  # signpost, a difficult visual negative
            d.rectangle((x + 7, y, x + 10, y + h), fill="#304050")
            d.rectangle((x - 2, y, x + w + 2, y + 12), fill="#d9ac32")
        else:
            d.ellipse((x + 4, y, x + w - 4, y + 12), fill="#304050")
            d.rectangle((x + 3, y + 12, x + w - 3, y + h), fill="#304050")
        if i == 6:
            d.ellipse((x - 8, y + 27, x + 23, y + 53), outline="#151515", width=2)
        if i == 8:
            d.rectangle((110, 25, 175, 90), outline="#aa5500", width=2)
        im.save(images / f"{i}.png")
    descriptions = [
        "seed omission",
        "omission",
        "already labeled",
        "zero-proposal omission",
        "signpost false alarm",
        "localization shift",
        "rider policy conflict",
        "seed duplicate",
        "ignore-region conflict",
    ]
    data = {
        "images": [
            {
                "id": str(i),
                "file_name": f"{i}.png",
                "width": 320,
                "height": 120,
                "metadata": {
                    "duplicate_group": "seed-group" if i in (0, 7) else None,
                    "ignore_regions": [[110, 25, 175, 90]] if i == 8 else [],
                },
            }
            for i in range(len(people))
        ],
        "categories": [{"id": 1, "name": "person"}, {"id": 2, "name": "cyclist"}],
        "annotations": [
            {"id": "a2", "image_id": "2", "category_id": 1, "bbox": list(people[2])},
            {"id": "a5", "image_id": "5", "category_id": 1, "bbox": [105, 32, 16, 50]},
            {"id": "a6", "image_id": "6", "category_id": 2, "bbox": [192, 35, 31, 53]},
        ],
    }
    predictions = [
        {
            "image_id": str(i),
            "category_id": 1,
            "bbox": list(p),
            "score": round(0.95 - i * 0.05, 2),
        }
        for i, p in enumerate(people)
        if i != 3
    ]
    truth = {
        "description": "Scripted synthetic truth; not human review",
        "cases": [
            {"image_id": str(i), "region": list(p), "case": descriptions[i]}
            for i, p in enumerate(people)
        ],
        "omitted_image_ids": ["0", "1", "3", "7"],
        "zero_proposal_image_ids": ["3"],
        "alternate_seed_image_id": "1",
    }
    for name, obj in [
        ("original.json", data),
        ("predictions.json", predictions),
        ("truth.json", truth),
    ]:
        (root / name).write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")
    (root / "policy.yml").write_text(
        'name: pedestrian-v1\ncategories:\n  person: pedestrian\n  cyclist: cyclist\nprediction_categories:\n  "1": pedestrian\n'
    )
    return root


def demo(workspace):
    workspace = Path(workspace)
    fixture = generate(workspace / "fixture")
    release = import_coco(
        workspace,
        fixture / "images",
        fixture / "original.json",
        fixture / "policy.yml",
        "fixture-v1",
    )
    index = index_predictions(
        workspace, release, fixture / "predictions.json", "scripted-fixture-v1"
    )
    incident = create_incident(
        workspace, release, "0", [20, 35, 38, 83], index["fingerprint"]
    )
    return {
        "release_id": release,
        "index_fingerprint": index["fingerprint"],
        "incident_id": incident,
    }
