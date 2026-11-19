import itertools
import math
import unittest
from avtriage.audit import draw, interval, report


class AuditTest(unittest.TestCase):
    def test_exact_coverage(self):
        for N in range(1, 9):
            for n in range(1, N + 1):
                for K in range(N + 1):
                    covered = sum(math.comb(K, x) * math.comb(N-K, n-x)
                                  for x in range(max(0, n-(N-K)), min(n, K)+1)
                                  if interval(N, n, x)[0] <= K <= interval(N, n, x)[1])
                    self.assertGreaterEqual(covered / math.comb(N, n), .95 - 1e-12)

    def test_census_zero_and_unresolved(self):
        self.assertEqual(interval(5, 5, 2), (2, 2))
        self.assertGreater(interval(100, 10, 0)[1], 0)
        design = draw({'zero': ['a', 'b'], 'high': ['c']}, 2, 42)
        self.assertEqual(len(design['draws']), 2)
        result = report(design, {})
        self.assertEqual(result['status'], 'unresolved')
        self.assertLessEqual(result['all_unknown_negative']['estimate'], result['all_unknown_positive']['estimate'])
        self.assertEqual(design, draw({'high': ['c'], 'zero': ['b', 'a']}, 2, 42))


if __name__ == '__main__':
    unittest.main()

class AuditWorkflowTest(unittest.TestCase):
    def test_independent_disagreement_and_adjudication(self):
        import tempfile
        from pathlib import Path
        from avtriage.fixture import demo
        from avtriage.audit_api import create_design, inspect, decide, result
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            fixture = demo(workspace)
            design = create_design(workspace, fixture['incident_id'], 2, 1)['design_id']
            blind = inspect(workspace, design)
            self.assertNotIn('proposals', str(blind))
            a, b = [im['id'] for im in blind['images']]
            first = decide(workspace, design, a, 'omission', 'human', 'alice')['id']
            decide(workspace, design, a, 'no_omission', 'human', 'bob')
            decide(workspace, design, b, 'no_omission', 'human', 'alice')
            self.assertEqual(result(workspace, design)['status'], 'unresolved')
            decide(workspace, design, a, 'omission', 'human_adjudicator', 'carol', first)
            self.assertEqual(result(workspace, design)['status'], 'complete')
            with self.assertRaises(ValueError): decide(workspace, design, a, 'omission', 'human', 'alice', first)

class AuditApiTest(unittest.TestCase):
    def test_blind_api(self):
        import tempfile
        from pathlib import Path
        from fastapi.testclient import TestClient
        from avtriage.api import create_app
        from avtriage.fixture import demo
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            incident = demo(workspace)['incident_id']
            client = TestClient(create_app(workspace))
            response = client.post('/api/audits', json={'incident_id': incident, 'budget': 2, 'seed': 7})
            self.assertEqual(response.status_code, 200)
            design = response.json()['design_id']
            blind = client.get(f'/api/audits/{design}/blind').json()
            self.assertEqual(len(blind['images']), 2)
            self.assertNotIn('proposal', str(blind))
            image_id = blind['images'][0]['id']
            self.assertEqual(client.post(f'/api/audits/{design}/decisions', json={'image_id':image_id,'decision':'unresolved','actor_type':'scripted_fixture','actor_id':'fixture'}).status_code, 200)
            self.assertEqual(client.get(f'/api/audits/{design}/result').json()['status'], 'unresolved')

class MultistratumCoverageTest(unittest.TestCase):
    def test_exhaustive_joint_draws(self):
        from itertools import product
        from math import comb
        from avtriage.audit import interval
        for K1 in range(4):
            for K2 in range(4):
                covered = 0
                for x1, x2 in product(range(2), repeat=2):
                    weight = comb(K1,x1)*comb(3-K1,1-x1)*comb(K2,x2)*comb(3-K2,1-x2)
                    a,b = interval(3,1,x1,.025); c,d = interval(3,1,x2,.025)
                    if a+c <= K1+K2 <= b+d: covered += weight
                self.assertGreaterEqual(covered/9, .95)
