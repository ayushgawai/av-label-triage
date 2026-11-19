import unittest
from avtriage.ranking import classify, rank

class RankingTest(unittest.TestCase):
    def test_matching_conflict_and_stable_fusion(self):
        p = [dict(id='a', image_id='1', bbox=[0,0,10,10], score=.9), dict(id='b', image_id='1', bbox=[0,0,10,10], score=.8), dict(id='c', image_id='2', bbox=[0,0,10,10], score=.7)]
        a = [dict(id='x', image_id='1', category='pedestrian', bbox=[0,0,10,10]),dict(id='y', image_id='2', category='cyclist', bbox=[0,0,10,10])]
        c = classify(p,a)
        self.assertEqual([v['match_status'] for v in c], ['already_labeled','crowded_conflict','cyclist_conflict'])
        result = rank(c,[1,0],{'b':[1,0], 'c':[0,1]})
        self.assertEqual([v['id'] for v in result],['b','c'])
        self.assertEqual(result,rank(list(reversed(c)),[1,0],{'b':[1,0],'c':[0,1]}))
        self.assertEqual([v['id'] for v in rank(c,[1,0],{},excluded_images=['1'])],['c'])

if __name__ == '__main__': unittest.main()

class PolicyTest(unittest.TestCase):
    def test_ignore_tiles_and_group_cap(self):
        p=[dict(id='a',image_id='1',bbox=[0,0,10,10],score=.8),dict(id='b',image_id='2',bbox=[0,0,10,10],score=None,group_id='drive'),dict(id='c',image_id='3',bbox=[0,0,10,10],score=.2,group_id='drive')]
        annotations=[dict(id='ignore',image_id='1',category='DontCare',bbox=[0,0,6,10])]
        rows=classify(p,annotations)
        self.assertEqual(rows[0]['match_status'],'out_of_scope')
        ranked=rank(rows,[1.,0.],{'b':[1.,0.],'c':[0.,1.]},method='similarity',max_per_group=1)
        self.assertEqual([r['id'] for r in ranked],['b'])
        self.assertIsNone(ranked[0]['confidence_rank'])
