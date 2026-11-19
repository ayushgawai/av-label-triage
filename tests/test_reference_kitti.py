import tempfile
import unittest
from pathlib import Path
from PIL import Image
from tools.reference_kitti import convert


class KittiAdapterTest(unittest.TestCase):
    def test_converts_and_clips(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            Image.new('RGB', (10, 10)).save(p / '000001.png')
            (p / '000001.txt').write_text('Pedestrian 0 0 0 -1 1 5 11 0 0 0 0 0 0 0\nDontCare 0 0 0 1 1 2 2 0 0 0 0 0 0 0\n')
            out = convert(p, p, {'dev':['000001'], 'drive_by_id':{'000001':'drive'}}, 'dev')
            self.assertEqual(out['annotations'][0]['bbox'], [0, 1, 5, 9])
            self.assertEqual(out['annotations'][1]['category_id'], 9)
            self.assertEqual(out['images'][0]['metadata']['drive_id'], 'drive')


if __name__ == '__main__': unittest.main()
