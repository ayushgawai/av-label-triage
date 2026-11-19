"""Opt-in asynchronous visual second opinions, separate from audit decisions."""
import base64
try:
    import fcntl
except ImportError:
    fcntl = None
import hashlib
import json
import sqlite3
import threading
import time
import urllib.request
from concurrent.futures import Future
from queue import PriorityQueue

QUESTION = 'Is the person mounted on a bicycle, walking beside it, or unclear? Return JSON with observation exactly mounted, walking_beside, or unclear, and cue as one short visible observation.'


def gemini_transport(model, api_key, images, question, timeout):
    parts=[{'text':question}] + [{'inline_data':{'mime_type':'image/jpeg','data':base64.b64encode(image).decode()}} for image in images]
    request=urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', data=json.dumps({'contents':[{'parts':parts}]}).encode(), headers={'Content-Type':'application/json','x-goog-api-key':api_key})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        data=json.load(response)
    return data['candidates'][0]['content']['parts'][0]['text']


class Flash:
    def __init__(self, db_path, *, enabled_releases, model, policies, api_key=None, transport=None, timeout=10, attempts=2):
        if fcntl is None: raise RuntimeError('Flash currently requires a Unix workspace lock')
        self.db_path=str(db_path);self._lock_file=open(self.db_path+'.lock','a+b');self.closed=False
        try: fcntl.flock(self._lock_file.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock_file.close();raise RuntimeError('Flash workspace already in use')
        self.enabled=set(enabled_releases);self.policies=policies;self.model=model;self.api_key=api_key;self.transport=transport or gemini_transport;self.timeout=timeout;self.attempts=attempts
        self.queue=PriorityQueue(); self.lock=threading.Lock();self.futures={};self.seq=0
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS flash_cases (release_id TEXT, incident_id TEXT, case_id TEXT, cache_key TEXT, status TEXT, response TEXT, attempts INTEGER DEFAULT 0, PRIMARY KEY(release_id,incident_id,case_id))')
            db.execute("UPDATE flash_cases SET status='interrupted' WHERE status IN ('queued','running')")
        for _ in range(2): threading.Thread(target=self._worker,daemon=True).start()

    def close(self):
        with self.lock:
            if self.closed: return
            self.closed=True
        self.queue.join()
        fcntl.flock(self._lock_file.fileno(),fcntl.LOCK_UN)
        self._lock_file.close()

    def db(self):
        return sqlite3.connect(self.db_path,timeout=30)

    def submit(self, *, release_id, incident_id, case_id, in_shortlist, reason, crop, frame, manual=False, prompt_revision='v1'):
        if self.closed: raise RuntimeError('Flash workspace is closed')
        if release_id not in self.enabled or not in_shortlist or reason != 'person_cyclist_conflict':
            raise ValueError('release opt-in, active shortlist and person/cyclist conflict required')
        policy=self.policies.get(release_id,{})
        if set(policy) != {'mounted','walking_beside','unclear'} or any(x not in ('pedestrian','out_of_scope','unresolved') for x in policy.values()): raise ValueError('complete release policy required')
        if self.transport is gemini_transport and not self.api_key: raise ValueError('provider key required')
        key=hashlib.sha256(json.dumps([self.model,prompt_revision,QUESTION,policy],sort_keys=True,separators=(',',':')).encode()+hashlib.sha256(crop).digest()+hashlib.sha256(frame).digest()).hexdigest()
        with self.lock:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT cache_key,status,response,attempts FROM flash_cases WHERE release_id=? AND incident_id=? AND case_id=?',(release_id,incident_id,case_id)).fetchone()
                if row and row[0] != key: raise ValueError('case already reserved with different content')
                if not row:
                    count=db.execute('SELECT count(*) FROM flash_cases WHERE release_id=? AND incident_id=?',(release_id,incident_id)).fetchone()[0]
                    if count >= 10: raise ValueError('incident case limit reached')
                    db.execute('INSERT INTO flash_cases VALUES (?,?,?,?,?,?,0)',(release_id,incident_id,case_id,key,'queued',None))
                elif row[1]=='complete':
                    f=Future();f.set_result(row[2]);return f
                elif row[3]>=self.attempts:
                    raise ValueError('case attempt limit reached')
                else: db.execute("UPDATE flash_cases SET status='queued' WHERE release_id=? AND incident_id=? AND case_id=?",(release_id,incident_id,case_id))
            identity=(release_id,incident_id,case_id)
            if identity in self.futures and not self.futures[identity].done(): return self.futures[identity]
            future=Future();self.futures[identity]=future;self.seq+=1
            self.queue.put((0 if manual else 1,self.seq,identity,key,crop,frame,future));return future

    def _worker(self):
        while True:
            _,_,identity,key,crop,frame,future=self.queue.get()
            try:
                deadline=time.monotonic()+self.timeout*self.attempts+0.25
                while True:
                    with self.db() as db:
                        db.execute('BEGIN IMMEDIATE'); row=db.execute('SELECT attempts FROM flash_cases WHERE release_id=? AND incident_id=? AND case_id=?',identity).fetchone()
                        if row[0] >= self.attempts: raise RuntimeError('case attempt limit reached')
                        db.execute("UPDATE flash_cases SET status='running',attempts=attempts+1 WHERE release_id=? AND incident_id=? AND case_id=?",identity)
                    try:
                        remaining=deadline-time.monotonic()
                        if remaining <= 0: raise TimeoutError('second opinion deadline exceeded')
                        result=self.transport(self.model,self.api_key,[crop,frame],QUESTION,min(self.timeout,remaining))
                        parsed=json.loads(result)
                        if not isinstance(parsed,dict) or parsed.get('observation') not in ('mounted','walking_beside','unclear') or not isinstance(parsed.get('cue'),str) or not parsed['cue'].strip() or len(parsed['cue'])>300: raise ValueError('invalid provider response')
                        result=json.dumps({'observation':parsed['observation'],'cue':parsed['cue'].strip(),'policy_outcome':self.policies[identity[0]][parsed['observation']]},separators=(',',':'))
                        if time.monotonic()>deadline: raise TimeoutError('second opinion deadline exceeded')
                        break
                    except Exception:
                        if row[0]+1 >= self.attempts or time.monotonic()+0.1 >= deadline: raise
                        time.sleep(0.1)
                with self.db() as db: db.execute("UPDATE flash_cases SET status='complete',response=? WHERE release_id=? AND incident_id=? AND case_id=?",(result,*identity))
                future.set_result(result)
            except Exception as exc:
                with self.db() as db: db.execute("UPDATE flash_cases SET status='failed' WHERE release_id=? AND incident_id=? AND case_id=?",identity)
                future.set_exception(exc)
            finally: self.queue.task_done()
