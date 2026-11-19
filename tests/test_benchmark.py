import unittest
from avtriage.benchmark import score


class BenchmarkTest(unittest.TestCase):
    def test_known_recovery_and_unknowns(self):
        refs = [{'id':'r1','image_id':'a','bbox':[0,0,10,10]}]
        queue = [{'image_id':'b','bbox':[0,0,10,10]}, {'image_id':'a','bbox':[0,0,10,10]}]
        r = score(queue, refs, ['a','b','c'], budgets=(1,2))
        self.assertEqual([x['known_boxes_recovered'] for x in r['budgets']], [0,1])
        self.assertEqual(r['eligible_images'], 3)
        with self.assertRaises(ValueError): score(queue + queue[:1], refs, ['a','b'])


if __name__ == '__main__': unittest.main()

class ScorecardTest(unittest.TestCase):
    def test_ceiling_and_random_are_reproducible(self):
        from avtriage.benchmark import scorecard
        ref = [{'id':'r', 'image_id':'a', 'bbox':[0,0,10,10]}]
        proposals = [{'id':'p', 'image_id':'a', 'bbox':[0,0,10,10]}]
        report = scorecard({'confidence': proposals}, proposals, ref, ['a','b'], budgets=(1,2))
        self.assertEqual(report['raw_detector_ceiling_known_boxes'], 1)
        self.assertEqual(report['random_full_frame'][-1]['known_images_reached'], 1)
        self.assertEqual(report, scorecard({'confidence': proposals}, proposals, ref, ['a','b'], budgets=(1,2)))
