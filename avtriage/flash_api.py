"""Explicitly configured, local-review-only Flash API."""
import io
import json
import os
from pathlib import Path
from fastapi import HTTPException
from PIL import Image, ImageDraw
from pydantic import BaseModel
from .core import connect, digest
from .flash import Flash
from .models import contextual_crop

class FlashRequest(BaseModel):
    proposal_id: str
    manual: bool = True


def register(app, workspace, incident_view):
    workspace=Path(workspace); config_path=workspace/'flash-opt-in.json'; engine=None
    if config_path.exists():
        config=json.loads(config_path.read_text())
        if config.get('enabled_releases') and config.get('model'):
            engine=Flash(workspace/'flash.sqlite',enabled_releases=config['enabled_releases'],model=config['model'],policies=config.get('policies',{}),api_key=os.environ.get('GEMINI_API_KEY'))

    @app.get('/api/flash/status')
    def flash_status():
        return {'enabled': bool(engine is not None and engine.api_key and engine.enabled)}

    @app.on_event('shutdown')
    def close_flash():
        if engine is not None: engine.close()

    @app.post('/api/incidents/{incident_id}/flash')
    def request_opinion(incident_id: str, body: FlashRequest):
        if engine is None: raise HTTPException(403,'Flash is not enabled for this workspace')
        result=incident_view(incident_id); case=result['incident']; active=result['proposals'][:10]
        proposal=next((p for p in active if p['id']==body.proposal_id),None)
        if proposal is None or proposal.get('match_status')!='cyclist_conflict': raise HTTPException(403,'candidate must be an active shortlist person/cyclist conflict')
        with connect(workspace) as db:
            image=db.execute('SELECT * FROM images WHERE release_id=? AND id=?',(case['release_id'],proposal['image_id'])).fetchone()
        path=Path(image['path']); raw=path.read_bytes()
        if digest(raw)!=image['sha256']: raise HTTPException(409,'media hash mismatch')
        with Image.open(io.BytesIO(raw)) as src:
            original=src.convert('RGB'); crop=contextual_crop(original,proposal['bbox']); marked=original.copy()
            ImageDraw.Draw(marked).rectangle(proposal['bbox'],outline='yellow',width=max(2,original.width//400))
            encoded=[]
            for im in (crop,marked):
                out=io.BytesIO();im.save(out,format='JPEG',quality=90);encoded.append(out.getvalue())
        try:
            engine.submit(release_id=case['release_id'],incident_id=incident_id,case_id=body.proposal_id,in_shortlist=True,reason='person_cyclist_conflict',crop=encoded[0],frame=encoded[1],manual=body.manual)
        except ValueError as exc: raise HTTPException(403,str(exc)) from exc
        return {'status':'queued','proposal_id':body.proposal_id,'note':'Second opinion is unverified and review remains local.'}

    @app.get('/api/incidents/{incident_id}/flash/{proposal_id}')
    def opinion(incident_id: str, proposal_id: str):
        if engine is None: raise HTTPException(403,'Flash is not enabled for this workspace')
        case=incident_view(incident_id)['incident']
        with engine.db() as db:
            row=db.execute('SELECT status,response,attempts FROM flash_cases WHERE release_id=? AND incident_id=? AND case_id=?',(case['release_id'],incident_id,proposal_id)).fetchone()
        if row is None: raise HTTPException(404,'No second opinion')
        return {'status':row[0],'response':json.loads(row[1]) if row[1] else None,'attempts':row[2],'model':engine.model}
