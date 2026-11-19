"""Fetch the two explicitly pinned Hugging Face model snapshots."""
from huggingface_hub import snapshot_download
from avtriage.models import DETECTOR, DETECTOR_REVISION, EMBEDDER, EMBEDDER_REVISION

def main():
    for name,revision in [(DETECTOR,DETECTOR_REVISION),(EMBEDDER,EMBEDDER_REVISION)]:
        print(snapshot_download(name,revision=revision,allow_patterns=['*.json','model.safetensors','README.md']))

if __name__=='__main__':main()
