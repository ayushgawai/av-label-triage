"""Run actual pinned CPU weights on a locally supplied image."""
import argparse
import tempfile
from pathlib import Path
from avtriage.models import FrozenModels, infer_image
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('image',type=Path)
a=p.parse_args()
with tempfile.TemporaryDirectory() as d:
    result=infer_image(FrozenModels('cpu'),a.image,Path(d))
    print('Person proposals:',len(result['proposals']))
    assert result['proposals'] and all(item['embedding'] for item in result['proposals'])
