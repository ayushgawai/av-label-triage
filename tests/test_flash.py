import tempfile, unittest, time
from pathlib import Path
from avtriage.flash import Flash
POLICY={"r":{"mounted":"out_of_scope","walking_beside":"pedestrian","unclear":"unresolved"}}

class FlashTest(unittest.TestCase):
    def test_optin_cache_and_boundaries(self):
        calls=[]
        def transport(*args): calls.append(1); time.sleep(.05); return '{"observation":"unclear","cue":"person is obscured"}'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db'; f=Flash(path,enabled_releases={'r'},model='test',policies=POLICY,transport=transport)
            kw=dict(release_id='r',incident_id='i',case_id='1',in_shortlist=True,reason='person_cyclist_conflict',crop=b'a',frame=b'b')
            with self.assertRaises(ValueError): f.submit(**{**kw,'release_id':'other'})
            a=f.submit(**kw);b=f.submit(**kw);self.assertIs(a,b);self.assertEqual(__import__('json').loads(a.result(timeout=2))['policy_outcome'],'unresolved')
            self.assertEqual(__import__('json').loads(f.submit(**kw).result())['observation'],'unclear');self.assertEqual(len(calls),1)
            with self.assertRaises(RuntimeError): Flash(path,enabled_releases={'r'},model='test',policies=POLICY,transport=transport)
            f.close()
            restarted=Flash(path,enabled_releases={'r'},model='test',policies=POLICY,transport=transport)
            self.assertEqual(__import__('json').loads(restarted.submit(**kw).result())['observation'],'unclear');self.assertEqual(len(calls),1)
            with self.assertRaises(ValueError): restarted.submit(**{**kw,'reason':'audit'})
            restarted.close()

if __name__=='__main__':unittest.main()

class FailureTest(unittest.TestCase):
    def test_bounded_retries_and_independent_review(self):
        calls=[]
        def fail(*args): calls.append(1); raise TimeoutError('offline')
        with tempfile.TemporaryDirectory() as tmp:
            f=Flash(Path(tmp)/'db',enabled_releases={'r'},model='test',policies=POLICY,transport=fail,timeout=.1,attempts=2)
            kw=dict(release_id='r',incident_id='i',case_id='1',in_shortlist=True,reason='person_cyclist_conflict',crop=b'a',frame=b'b')
            with self.assertRaises(TimeoutError): f.submit(**kw).result(timeout=2)
            self.assertEqual(len(calls),2)
            with self.assertRaises(ValueError): f.submit(**kw)

class ApiTest(unittest.TestCase):
    def test_disabled_endpoint_makes_no_calls(self):
        from fastapi.testclient import TestClient
        from avtriage.api import create_app
        with tempfile.TemporaryDirectory() as tmp:
            client=TestClient(create_app(tmp))
            result=client.post('/api/incidents/none/flash',json={'proposal_id':'none'})
            self.assertEqual(result.status_code,403)
            self.assertFalse((Path(tmp)/'flash.sqlite').exists())

    def test_enabled_route_uses_server_context_only(self):
        import json
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from avtriage.fixture import demo
        from avtriage.api import create_app
        calls=[]
        def fake(*args): calls.append(args);return '{"observation":"unclear","cue":"person is obscured"}'
        def factory(*args,**kwargs): kwargs['transport']=fake;return Flash(*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            ids=demo(tmp);root=Path(tmp)
            (root/'flash-opt-in.json').write_text(json.dumps({'enabled_releases':[ids['release_id']],'model':'mock','policies':{ids['release_id']:POLICY['r']}}))
            with patch('avtriage.flash_api.Flash',side_effect=factory): client=TestClient(create_app(tmp))
            queue=client.get('/api/incidents/'+ids['incident_id']).json()['proposals']
            p=next(x for x in queue if x['match_status']=='cyclist_conflict')
            other=next(x for x in queue if x['match_status']=='unmatched')
            url='/api/incidents/'+ids['incident_id']+'/flash'
            self.assertEqual(client.post(url,json={'proposal_id':other['id']}).status_code,403)
            self.assertEqual(client.post(url,json={'proposal_id':p['id']}).status_code,200)
            for _ in range(50):
                result=client.get(url+'/'+p['id']).json()
                if result['status']=='complete': break
                time.sleep(.01)
            self.assertEqual(result['response']['policy_outcome'],'unresolved');self.assertEqual(len(calls),1)
            self.assertNotIn('flash',client.get('/api/incidents/'+ids['incident_id']).json())

class LimitsTest(unittest.TestCase):
    def test_case_limit_response_validation_and_concurrency(self):
        import threading
        active=0; maximum=0; lock=threading.Lock()
        def fake(*args):
            nonlocal active,maximum
            with lock: active+=1;maximum=max(maximum,active)
            time.sleep(.02)
            with lock: active-=1
            return '{"observation":"mounted","cue":"feet on pedals"}'
        with tempfile.TemporaryDirectory() as tmp:
            f=Flash(Path(tmp)/'db',enabled_releases={'r'},model='test',policies=POLICY,transport=fake)
            kw=dict(release_id='r',incident_id='i',in_shortlist=True,reason='person_cyclist_conflict',crop=b'a',frame=b'b')
            futures=[f.submit(case_id=str(i),**kw) for i in range(10)]
            with self.assertRaises(ValueError): f.submit(case_id='10',**kw)
            for future in futures: self.assertEqual(__import__('json').loads(future.result(timeout=2))['policy_outcome'],'out_of_scope')
            self.assertLessEqual(maximum,2); f.close()
        with tempfile.TemporaryDirectory() as tmp:
            f=Flash(Path(tmp)/'db',enabled_releases={'r'},model='test',policies=POLICY,transport=lambda *args:'{"observation":"maybe","cue":"x"}',attempts=1)
            with self.assertRaises(ValueError): f.submit(case_id='1',**kw).result(timeout=2)
            f.close()
