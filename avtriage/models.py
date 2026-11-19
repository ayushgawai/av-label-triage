"""Optional frozen Hugging Face inference; no corrected labels are loaded."""
import hashlib
import importlib.metadata
import platform
import json
import os
from pathlib import Path

DETECTOR = 'PekingU/rtdetr_r50vd'
DETECTOR_REVISION = 'df939e661d8c52e80608d1ec566561aabd25a4e7'
EMBEDDER = 'facebook/dinov2-small'
EMBEDDER_REVISION = 'ed25f3a31f01632728cabb09d1542f84ab7b0056'


def contextual_crop(image, bbox, context=0.2):
    x1, y1, x2, y2 = map(float, bbox)
    if not (0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height and 0 <= context <= 1):
        raise ValueError('invalid crop bounds or context')
    w, h = x2-x1, y2-y1
    return image.crop((max(0, int(x1-w*context)), max(0, int(y1-h*context)), min(image.width, int(x2+w*context+0.999999)), min(image.height, int(y2+h*context+0.999999))))


def tiles(width, height):
    """A fixed 2x2 half-overlap grid; tile is a hint, not a box prediction."""
    w, h = width*2/3, height*2/3
    return [[x,y,x+w,y+h] for y in (0.,height-h) for x in (0.,width-w)]


class FrozenModels:
    def __init__(self, device='cpu'):
        import torch
        from transformers import AutoImageProcessor, AutoModel, RTDetrImageProcessor, RTDetrForObjectDetection
        self.torch, self.device = torch, device
        self.detector_processor = RTDetrImageProcessor.from_pretrained(DETECTOR, revision=DETECTOR_REVISION, local_files_only=True, use_fast=False)
        self.detector = RTDetrForObjectDetection.from_pretrained(DETECTOR, revision=DETECTOR_REVISION, local_files_only=True).to(device).eval()
        self.embedding_processor = AutoImageProcessor.from_pretrained(EMBEDDER, revision=EMBEDDER_REVISION, local_files_only=True, use_fast=False)
        self.embedder = AutoModel.from_pretrained(EMBEDDER, revision=EMBEDDER_REVISION, local_files_only=True).to(device).eval()

    def detect(self, image, threshold=.05):
        inputs = self.detector_processor(images=image, return_tensors='pt').to(self.device)
        with self.torch.inference_mode():
            result = self.detector_processor.post_process_object_detection(self.detector(**inputs), threshold=threshold, target_sizes=self.torch.tensor([[image.height,image.width]], device=self.device))[0]
        detections = []
        for box, score, label in zip(result['boxes'].cpu().tolist(),result['scores'].cpu().tolist(),result['labels'].cpu().tolist()):
            box = [max(0., min(float(image.width), box[0])), max(0., min(float(image.height), box[1])), max(0., min(float(image.width), box[2])), max(0., min(float(image.height), box[3]))]
            if label == 0 and box[2] > box[0] and box[3] > box[1]: detections.append({'bbox': box, 'score': float(score)})
        return detections

    def embed(self, images):
        if not images: return []
        inputs = self.embedding_processor(images=images, return_tensors='pt').to(self.device)
        with self.torch.inference_mode():
            v = self.embedder(**inputs).last_hidden_state[:,0,:]
            v = self.torch.nn.functional.normalize(v, dim=1)
        return v.cpu().tolist()


def infer_image(model, path, cache_dir, threshold=.05):
    """Resume only on identical bytes and model/config fingerprint; replace shard atomically."""
    from PIL import Image, ImageOps
    path, cache_dir = Path(path), Path(cache_dir)
    raw = path.read_bytes()
    versions = {}
    for name in ('torch', 'transformers', 'pillow', 'numpy'):
        try: versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name] = None
    settings = {'detector_revision': DETECTOR_REVISION, 'embedder_revision': EMBEDDER_REVISION, 'threshold': threshold, 'context': .2, 'batch_size': 16, 'processor': 'slow', 'device': getattr(model, 'device', 'stub'), 'python': platform.python_version(), 'packages': versions}
    fingerprint = hashlib.sha256(raw + json.dumps(settings, sort_keys=True, separators=(',',':')).encode()).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / (fingerprint + '.json')
    if dest.exists(): return json.loads(dest.read_text())
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
        detections = model.detect(image, threshold)
        for start in range(0, len(detections), 16):
            batch = detections[start:start+16]
            for item, embedding in zip(batch, model.embed([contextual_crop(image,p['bbox']) for p in batch])):
                item['embedding'] = embedding
    result = {'fingerprint':fingerprint, 'image_sha256':hashlib.sha256(raw).hexdigest(), 'detector_revision':DETECTOR_REVISION, 'embedder_revision':EMBEDDER_REVISION, 'threshold':threshold, 'settings':settings, 'proposals':detections}
    temp = dest.with_name(dest.name + f'.{os.getpid()}.tmp')
    try:
        temp.write_text(json.dumps(result, allow_nan=False, separators=(',',':')))
        os.replace(temp, dest)
    finally:
        temp.unlink(missing_ok=True)
    return result
