"""Live Cast v0.2 — protected SIMULATION for localhost and Render testing.

WARNING: This is not connected to live YouTube, and Render's demo SQLite is ephemeral.
Remote mode demands two separate secrets: an operator password and a read-only viewer token.
"""
from __future__ import annotations
import csv
import io
import os
import re
import secrets
import base64
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import store
from core import parse_amount_to_micros

ROOT = Path(__file__).resolve().parent
REMOTE_TEST = os.getenv('LIVECAST_REMOTE_TEST', '0') == '1'
OPERATOR_PASSWORD = os.getenv('OPERATOR_PASSWORD', '')
VIEW_TOKEN = os.getenv('VIEW_TOKEN', '')


def _operator_ok(request: Request) -> bool:
    header = request.headers.get('Authorization', '')
    if not header.startswith('Basic '):
        return False
    try:
        raw = base64.b64decode(header[6:], validate=True).decode('utf-8')
        username, password = raw.split(':', 1)
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return False
    return secrets.compare_digest(username, 'operator') and secrets.compare_digest(password, OPERATOR_PASSWORD)


def _viewer_ok(request: Request) -> bool:
    provided = request.query_params.get('view_token', '') or request.headers.get('X-View-Token', '')
    return bool(provided) and secrets.compare_digest(provided, VIEW_TOKEN)


def _viewer_route(request: Request) -> bool:
    if request.method != 'GET':
        return False
    path = request.url.path
    if path in ('/producers', '/api/state', '/api/alerts'):
        return True
    if re.fullmatch(r'/overlay/[a-z0-9_-]+', path):
        return request.query_params.get('preview') != '1'
    if re.fullmatch(r'/api/graphics/[a-z0-9_-]+', path):
        return request.query_params.get('preview', '').lower() not in ('1','true','yes','on')
    return False



@asynccontextmanager
async def lifespan(app: FastAPI):
    if REMOTE_TEST:
        if len(OPERATOR_PASSWORD) < 12 or len(VIEW_TOKEN) < 24:
            raise RuntimeError('Remote simulation requires OPERATOR_PASSWORD (12+ characters) and VIEW_TOKEN (24+ characters).')
        if secrets.compare_digest(OPERATOR_PASSWORD, VIEW_TOKEN):
            raise RuntimeError('Operator password and viewer token must differ.')
    store.initialize()
    yield

app = FastAPI(title='Live Cast Scoreboard — Haiti Simulation 0.2', lifespan=lifespan,
              docs_url=None, redoc_url=None)


@app.middleware('http')
async def remote_test_auth(request: Request, call_next):
    if REMOTE_TEST and request.url.path != '/health' and not request.url.path.startswith(('/css/', '/js/')):
        if not _operator_ok(request) and not (_viewer_route(request) and _viewer_ok(request)):
            return Response(status_code=401, content='Operator login or authorized read-only link required',
                            headers={'WWW-Authenticate':'Basic realm="Live Cast Demo Operator"',
                                     'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer'})
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

app.mount('/css', StaticFiles(directory=ROOT / 'css'), name='css')
app.mount('/js', StaticFiles(directory=ROOT / 'js'), name='js')

@app.get('/')
def home():
    return FileResponse(ROOT / 'index.html')

@app.get('/producers')
def producer_page():
    return FileResponse(ROOT / 'producer.html')

@app.get('/overlay/{graphic_id}')
def overlay_page(graphic_id: str):
    if store.get_graphic(graphic_id) is None:
        raise HTTPException(404, 'Unknown graphic')
    return FileResponse(ROOT / 'overlay.html')

@app.get('/health')
def health():
    return {'ok':True, 'mode':'simulation', 'storage':'ephemeral-sqlite' if REMOTE_TEST else 'local-sqlite', 'version':'0.2.0', 'youtube_connected': False}

@app.get('/api/state')
def state():
    return store.state()

@app.get('/api/alerts')
def alerts(after: int = 0, limit: int = 100):
    return {'alerts':store.alerts(max(0, after), limit)}

class TestDonation(BaseModel):
    amount: str = Field(default='20.00', max_length=30)
    message: str = Field(default='#Marcus', max_length=500)
    donor: str = Field(default='Test Viewer', max_length=100)
    kind: Literal['superChatEvent','superStickerEvent','textMessageEvent'] = 'superChatEvent'
    currency: Literal['USD','EUR','CAD','HTG'] = 'USD'
    event_id: str | None = Field(default=None, max_length=100)

@app.post('/api/simulate')
def simulate(data: TestDonation):
    try:
        amount_micros = parse_amount_to_micros(data.amount)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    field = 'superChatDetails' if data.kind == 'superChatEvent' else 'superStickerDetails'
    snippet = {'type':data.kind, 'publishedAt':datetime.now(timezone.utc).isoformat(),
               field:{'amountMicros':str(amount_micros), 'currency':data.currency,
                      'amountDisplayString':f'{data.currency} {data.amount}',
                      'userComment':data.message}}
    if data.kind == 'textMessageEvent':
        snippet = {'type':data.kind, 'textMessageDetails':{'messageText':data.message}}
    event_id = data.event_id.strip() if data.event_id else f'simulation-{uuid.uuid4().hex}'
    try:
        result = store.ingest({'id':event_id, 'snippet':snippet,
                               'authorDetails':{'displayName':data.donor}})
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return result

class Assignment(BaseModel):
    donation_id: str = Field(min_length=1, max_length=100)
    cast_id: str = Field(min_length=1, max_length=50)
    reason: str = Field(default='Producer review', min_length=3, max_length=250)

@app.post('/api/assign')
def assign(data: Assignment):
    try:
        return store.assign(data.donation_id, data.cast_id, data.reason)
    except ValueError as exc:
        raise HTTPException(400,str(exc))

class ScoreSettings(BaseModel):
    points_per_usd: str = Field(max_length=25)

@app.put('/api/settings')
def change_settings(data: ScoreSettings):
    try:
        store.set_multiplier(data.points_per_usd)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    return {'ok':True,'points_per_usd':store.state()['points_per_usd']}

class Member(BaseModel):
    id: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    hashtags: list[str] = Field(min_length=1, max_length=15)
    active: bool = True

@app.post('/api/cast')
def update_cast(data: Member):
    try:
        return store.cast_upsert(data.model_dump())
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.get('/api/graphics')
def get_graphics():
    return {'graphics':store.get_graphics()}

@app.get('/api/graphics/{graphic_id}')
def get_graphic(graphic_id: str, preview: bool = False):
    data = store.get_graphic(graphic_id, preview=preview)
    if not data:
        raise HTTPException(404, 'Unknown graphic')
    return data

class GraphicDraft(BaseModel):
    name: str = Field(min_length=1,max_length=70)
    accent: str
    position: Literal['left','center','right']
    scale: Literal['small','normal','large']
    title_en: str = Field(max_length=70)
    title_ht: str = Field(max_length=70)
    duration: int = Field(ge=2,le=20)
    enabled: bool = True

@app.put('/api/graphics/{graphic_id}/draft')
def edit_graphic(graphic_id: str, data: GraphicDraft):
    try:
        return store.draft_graphic(graphic_id,data.model_dump())
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.post('/api/graphics/{graphic_id}/publish')
def publish_graphic(graphic_id: str):
    try:
        return store.publish_graphic(graphic_id)
    except ValueError as exc:
        raise HTTPException(400,str(exc))

class NewGraphic(BaseModel):
    source_id: str
    id: str
    name: str = Field(min_length=1,max_length=70)

@app.post('/api/graphics')
def clone_graphic(data: NewGraphic):
    try:
        return store.clone_graphic(data.source_id,data.id,data.name)
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.get('/api/export/donations.csv')
def export_donations():
    rows = store.export_rows()
    output = io.StringIO()
    names = ['id','kind','donor','message','amount_micros','currency','amount_display',
             'cast_id','status','points_milli','published_at','received_at']
    writer = csv.DictWriter(output, fieldnames=names)
    writer.writeheader()
    for row in rows:
        # Protect CSV consumers against formula injection from viewer-controlled text.
        for k in ('donor','message'):
            if row[k].lstrip().startswith(('=','+','-','@')):
                row[k] = "'" + row[k]
        writer.writerow(row)
    output.seek(0)
    return Response(content=output.read(),media_type='text/csv',headers={
        'Content-Disposition':'attachment; filename="test-donations.csv"'})

class Reset(BaseModel):
    confirm: str

@app.post('/api/reset')
def reset(data: Reset):
    if data.confirm != 'RESET DEMO':
        raise HTTPException(400, 'Confirmation must be RESET DEMO')
    store.reset_simulation()
    return {'ok':True}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000, workers=1)
