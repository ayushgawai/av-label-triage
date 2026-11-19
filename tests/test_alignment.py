import tempfile
import unittest
from pathlib import Path

from PIL import Image
from tools.alignment import inventory, pair


class AlignmentTest(unittest.TestCase):
    def test_exact_resize_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = root / 'a', root / 'b'
            a.mkdir(); b.mkdir()
            Image.new('RGB', (80, 60), 'red').save(a / 'one.png')
            Image.new('RGB', (80, 60), 'red').save(b / 'exact.png')
            self.assertEqual(pair(inventory(a), inventory(b))[0]['status'], 'exact')
            Image.new('RGB', (40, 30), 'red').save(b / 'resized.png')
            rows = pair(inventory(a), inventory(b))
            self.assertEqual([r['status'] for r in rows], ['ambiguous', 'ambiguous'])
            (b / 'exact.png').unlink()
            self.assertEqual(pair(inventory(a), inventory(b))[0]['status'], 'proposed_review')
            Image.new('RGB', (80, 60), 'blue').save(b / 'different.png')
            self.assertEqual(pair(inventory(a), inventory(b))[0]['status'], 'unmatched')


if __name__ == '__main__':
    unittest.main()
