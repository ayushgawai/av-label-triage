import tempfile
import unittest
from pathlib import Path
from PIL import Image
from avtriage.models import contextual_crop, infer_image, tiles

class Stub:
    def __init__(self): self.calls = 0
    def detect(self, image, threshold): self.calls += 1; return [{'bbox':[1,1,5,5],'score':.7}]
    def embed(self, images): return [[1.,0.] for _ in images]

class ModelTest(unittest.TestCase):
    def test_crop_and_fingerprint_resume(self):
        im = Image.new('RGB',(10,10),'red')
        self.assertEqual(contextual_crop(im,[1,1,5,5]).size,(6,6))
        self.assertEqual(len(tiles(10,10)),4)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'im.png'; im.save(path); model=Stub()
            a=infer_image(model,path,Path(tmp)/'cache')
            self.assertEqual(a,infer_image(model,path,Path(tmp)/'cache'))
            self.assertEqual(model.calls,1)
            infer_image(model,path,Path(tmp)/'cache',.1)
            self.assertEqual(model.calls,2)
        with self.assertRaises(ValueError): contextual_crop(im,[0,0,11,1])

if __name__ == '__main__': unittest.main()
