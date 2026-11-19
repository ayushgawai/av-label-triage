import unittest
from collections import defaultdict
from tools.reference_compare import compare, eligible, iou


class ReferenceComparisonTest(unittest.TestCase):
    def test_geometry_and_greedy_matching(self):
        box = (0, 0, 10, 10)
        self.assertEqual(iou(box, (5, 0, 15, 10)), 1 / 3)
        self.assertFalse(eligible(box, [(0, 0, 5, 10)], 0, True))
        originals = defaultdict(list, {'a.png': [box]})
        row = dict(filename='a.png', probability='1', height='10', xmin='0', ymin='0', xmax='10', ymax='10')
        self.assertEqual(compare([row, row], originals, defaultdict(list), height=0),
                         {'matched': 1, 'overlooked': 1, 'misfitting': 0})

    def test_partial_overlap_is_misfitting(self):
        row = dict(filename='a.png', probability='1', height='10', xmin='5', ymin='0', xmax='15', ymax='10')
        self.assertEqual(compare([row], {'a.png': [(0, 0, 10, 10)]}, defaultdict(list), height=0)['misfitting'], 1)


if __name__ == '__main__':
    unittest.main()
