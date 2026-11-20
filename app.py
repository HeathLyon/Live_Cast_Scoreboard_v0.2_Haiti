"""Live Cast production foundation. Real YouTube scoring is isolated from simulation in production."""
from __future__ import annotations
import asyncio
import csv
import io
import os
import re
import secrets
import base64
import json
import hashlib
import mimetypes
import uuid
import tempfile
from datetime import timedelta
from time import monotonic
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

import store
import ops
from core import parse_amount_to_micros
from youtube_monitor import YouTubeMonitor, video_id_from_input

ROOT = Path(__file__).resolve().parent
# The GitHub repository keeps its HTML, CSS, and JS at the root.
WEB = ROOT
REMOTE_TEST = os.getenv('LIVECAST_REMOTE_TEST', '0') == '1'
OPERATOR_PASSWORD = os.getenv('OPERATOR_PASSWORD', '')
VIEW_TOKEN = os.getenv('VIEW_TOKEN', '')
# Public *broadcast-only* data. The operator API and full transaction ledger stay private.
PUBLIC_OVERLAYS = os.getenv('PUBLIC_OVERLAYS', '0') == '1'
PAGES_ORIGIN = os.getenv('PAGES_ORIGIN', 'https://heathlyon.github.io').rstrip('/')
STARTED = monotonic()


def _principal(request: Request) -> dict | None:
    """HTTP Basic identities (hashed, per-person secrets) or staging legacy operator.

    Production must provide named users via LIVECAST_USERS_JSON. Never put raw
    passwords or hashes in the repo or GitHub Pages scripts.
    """
    header=request.headers.get('Authorization','')
    if not header.startswith('Basic '):return None
    try:
        raw=base64.b64decode(header[6:],validate=True).decode('utf-8')
        username,password=raw.split(':',1)
    except (ValueError,UnicodeDecodeError,base64.binascii.Error):return None
    configured=os.getenv('LIVECAST_USERS_JSON','').strip()
    if configured:
        try:
            users=json.loads(configured)
            item=users.get(username)
            if not isinstance(item,dict):return None
            role=item.get('role')
            if role not in ('admin','producer','viewer'):return None
            match=ops.PASSWORD_HASH.fullmatch(item.get('password_hash',''))
            if not match:return None
            salt,expected=match.groups()
            derived=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
            return {'username':username,'role':role} if secrets.compare_digest(derived,expected) else None
        except (ValueError,TypeError,KeyError,AttributeError,MemoryError):return None
    # Shared operator credentials are allowed for existing staging installs ONLY.
    if ops.PROFILE=='production':return None
    if username=='operator' and OPERATOR_PASSWORD and secrets.compare_digest(password.encode(),OPERATOR_PASSWORD.encode()):
        return {'username':'operator','role':'admin'}
    return None


def _actor(request: Request) -> str:
    return getattr(request.state, 'operator_identity', {}).get('username', 'operator')


def _role_allows(request:Request,principal:dict) -> bool:
    path=request.url.path;method=request.method
    role=principal['role']
    if role=='admin':return True
    if path.startswith('/api/debug/') or path in ('/api/simulate','/api/reset','/api/system/backup.sqlite3',
                 '/api/export/donations.csv'):
        return False
    if role=='viewer':return method in ('GET','HEAD')
    # Producers can reconcile donations, operate broadcast and create graphics;
    # server connection/scoring configuration stays with administrators.
    if path in ('/api/settings','/api/youtube/config') and method not in ('GET','HEAD'):
        return False
    return True


def _viewer_ok(request: Request) -> bool:
    provided = request.query_params.get('view_token', '') or request.headers.get('X-View-Token', '')
    return bool(provided) and secrets.compare_digest(provided.encode(), VIEW_TOKEN.encode())


def _public_route(request: Request) -> bool:
    if not PUBLIC_OVERLAYS or request.method != 'GET':
        return False
    path = request.url.path
    return path in ('/public/state', '/public/alerts', '/public/goals', '/public/playback') or bool(re.fullmatch(r'/public/graphics/[a-z0-9_-]+', path))


def _viewer_route(request: Request) -> bool:
    if request.method != 'GET':
        return False
    path = request.url.path
    if path in ('/producers', '/api/state', '/api/alerts', '/api/overlay/goals', '/api/playback'):
        return True
    if re.fullmatch(r'/overlay/[a-z0-9_-]+', path):
        return request.query_params.get('preview') != '1'
    if re.fullmatch(r'/api/graphics/[a-z0-9_-]+', path):
        return request.query_params.get('preview', '').lower() not in ('1','true','yes','on')
    return False



youtube_monitor = YouTubeMonitor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if REMOTE_TEST:
        if len(VIEW_TOKEN) < 24 or (not os.getenv('LIVECAST_USERS_JSON') and len(OPERATOR_PASSWORD) < 12):
            raise RuntimeError('Remote mode requires a viewer token and operator credentials.')
        if OPERATOR_PASSWORD and secrets.compare_digest(OPERATOR_PASSWORD.encode(),VIEW_TOKEN.encode()):
            raise RuntimeError('Operator password and viewer token must differ.')
    ops.check_production_config()
    store.initialize()
    app.state.auth_slots = asyncio.Semaphore(2)
    stop_youtube = asyncio.Event()
    task = asyncio.create_task(youtube_monitor.run(stop_youtube))
    async def run_broadcast_queue():
        while not stop_youtube.is_set():
            try:
                await asyncio.to_thread(store.advance_broadcast)
            except Exception:  # The operator status panel will flag DB faults.
                pass
            await asyncio.sleep(0.5)
    broadcast_task = asyncio.create_task(run_broadcast_queue())
    try:
        yield
    finally:
        stop_youtube.set()
        youtube_monitor.configuration_changed()
        await task
        await broadcast_task

app = FastAPI(title='Live Cast Scoreboard — Production Control Room 1.1', lifespan=lifespan,
              docs_url=None, redoc_url=None)


@app.middleware('http')
async def remote_test_auth(request: Request, call_next):
    if REMOTE_TEST and request.url.path != '/health' and not request.url.path.startswith(('/css/', '/js/', '/overlay/css/', '/overlay/js/')):
        principal = None
        if request.headers.get('Authorization', '').startswith('Basic '):
            async with request.app.state.auth_slots:
                principal = await asyncio.to_thread(_principal, request)
        if principal:
            request.state.operator_identity=principal
            if not _role_allows(request,principal):
                return Response(status_code=403,content='Insufficient permission')
            if request.method not in ('GET','HEAD','OPTIONS'):
                origin=request.headers.get('Origin')
                if origin and origin.rstrip('/') not in (ops.PUBLIC_BASE, str(request.base_url).rstrip('/')):
                    return Response(status_code=403,content='Cross-origin operator action blocked')
        elif not (_viewer_route(request) and _viewer_ok(request)) and not _public_route(request):
            return Response(status_code=401, content='Operator login or authorized read-only link required',
                            headers={'WWW-Authenticate':'Basic realm="Live Cast Control Room"',
                                     'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer'})
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

# Serve only public CSS and JS folders. Never expose the repository root via StaticFiles.
# Root HTML pages use relative assets: /css/ and /js/.
# The nested /overlay/{id} URL resolves relative assets to /overlay/css and /overlay/js.
# Cross-origin reads are restricted to the GitHub Pages site. No credentials are shared.
mimetypes.add_type('text/javascript', '.js')
app.add_middleware(CORSMiddleware, allow_origins=[PAGES_ORIGIN],
                   allow_methods=['GET'], allow_headers=['Accept', 'Content-Type'],
                   allow_credentials=False)

app.mount('/css', StaticFiles(directory=str(ROOT / 'css')), name='css')
app.mount('/js', StaticFiles(directory=str(ROOT / 'js')), name='js')
app.mount('/overlay/css', StaticFiles(directory=str(ROOT / 'css')), name='overlay-css')
app.mount('/overlay/js', StaticFiles(directory=str(ROOT / 'js')), name='overlay-js')

@app.get('/')
def home():
    return FileResponse(WEB / 'index.html')

@app.get('/producers')
def producer_page():
    return FileResponse(WEB / 'producer.html')

@app.get('/overlay/{graphic_id}')
def overlay_page(graphic_id: str):
    if graphic_id not in ('goals', 'top3-alert') and store.get_graphic(graphic_id) is None:
        raise HTTPException(404, 'Unknown graphic')
    return FileResponse(WEB / 'overlay.html')

@app.get('/health')
def health():
    return {'ok':True, 'mode':'production' if store.LIVE_MODE else 'staging',
            'storage':'persistent-single-node-sqlite' if store.LIVE_MODE else ('ephemeral-sqlite' if REMOTE_TEST else 'local-sqlite'),
            'version':'1.1.0-rc1', 'profile':ops.PROFILE, 'youtube_connected': youtube_monitor.connected,
            'public_overlays_enabled': PUBLIC_OVERLAYS}

@app.get('/public/state')
def public_state():
    """Broadcast-only snapshot. Never expose the private operator's donations or review queues."""
    if not PUBLIC_OVERLAYS:
        raise HTTPException(404, 'Public overlay feed disabled')
    s = store.state()
    public_rank = lambda m: {k: m[k] for k in ('id', 'name', 'rank', 'points')}
    return {'mode': s['mode'], 'live_mode':s['live_mode'], 'revision': s['revision'],
            'updated_at': s['updated_at'], 'last_alert_id': s['last_alert_id'],
            'broadcast_queue_enabled':store.QUEUE_MODE,
            'top3': [public_rank(m) for m in s['top3']],
            'ranking': [public_rank(m) for m in s['ranking']]}


@app.get('/public/alerts')
def public_alerts(after: int = 0, limit: int = 100, check_after: int | None = None):
    if not PUBLIC_OVERLAYS:
        raise HTTPException(404, 'Public overlay feed disabled')
    safe = ('seq', 'cast_name', 'delta_points', 'new_total', 'rank')
    data = alerts(after, limit, check_after)
    data['alerts'] = [{k: e[k] for k in safe} for e in data['alerts']]
    return data


@app.get('/public/graphics/{graphic_id}')
def public_graphic(graphic_id: str):
    if not PUBLIC_OVERLAYS:
        raise HTTPException(404, 'Public overlay feed disabled')
    config = store.get_graphic(graphic_id, preview=False)
    if not config:
        raise HTTPException(404, 'Unknown graphic')
    safe = ('id','name','kind','accent','position','scale','title_en','title_ht','duration','enabled')
    return {k: config[k] for k in safe if k in config}



@app.get('/public/goals')
def public_goals():
    if not PUBLIC_OVERLAYS:
        raise HTTPException(404, 'Public overlay feed disabled')
    return overlay_goals()

@app.get('/api/overlay/goals')
def overlay_goals():
    return {**store.goals_state(public=True), 'live_mode': store.LIVE_MODE}

@app.get('/public/playback')
def public_playback():
    if not PUBLIC_OVERLAYS:
        raise HTTPException(404, 'Broadcast feed disabled')
    return overlay_playback()

@app.get('/api/playback')
def overlay_playback():
    return store.broadcast_status(public=True)

@app.get('/api/system/status')
def system_status(request: Request):
    try:
        storage=store.storage_status()
    except Exception as error:
        storage={'database_ok':False,'error':type(error).__name__}
    youtube=youtube_monitor.snapshot()
    return {'version':'1.1.0-rc1','environment':ops.PROFILE,
            'production_isolated':store.LIVE_MODE,
            'operator':getattr(request.state,'operator_identity',{'username':'operator','role':'admin'}),
            'uptime_seconds':round(monotonic()-STARTED),
            'backend_url':ops.PUBLIC_BASE,'pages_url':ops.PAGES_BASE,
            'graphics':ops.graphic_links(),
            'connections':{'database':bool(storage.get('database_ok')),
                           'youtube_api_key':youtube['api_key_configured'],
                           'youtube_listening':youtube['connected'],
                           'public_overlays':PUBLIC_OVERLAYS},
            'storage':{**storage,'kind':'persistent-single-node-sqlite' if store.LIVE_MODE else 'staging-sqlite',
                       'persistent_root_configured':bool(os.getenv('LIVECAST_PERSISTENT_ROOT'))},
            'youtube':youtube,'broadcast':store.broadcast_status(), 'cast_summary':store.cast_summary(),
            'graphic_readiness':{**{g['id']:{'enabled':bool(g['published']['enabled']),'type':g['published']['kind']} for g in store.get_graphics()},
                'goals':{'enabled':store.goals_state()['visible'] and any(x['enabled'] for x in store.goals_state()['goals']), 'type':'goals'}},
            'notes':['Production uses only real YouTube messages for scores and on-air alerts.',
                     'Test events are retained for debugging but never alter live rankings.',
                     'A persistent disk, backups, auth hardening and end-to-end validation remain required.']}

class QueueControl(BaseModel):
    action: Literal['pause','resume','skip','group_on','group_off']

@app.post('/api/system/broadcast')
def queue_control(data: QueueControl, request: Request):
    try:
        return store.control_broadcast(data.action, actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.get('/api/system/backup.sqlite3')
def download_backup():
    fd,path=tempfile.mkstemp(prefix='livecast-backup-',suffix='.sqlite3')
    os.close(fd)
    try:
        store.backup_sqlite(path)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return FileResponse(path,media_type='application/vnd.sqlite3',
                        filename='livecast-backup.sqlite3',
                        background=BackgroundTask(lambda:Path(path).unlink(missing_ok=True)))

@app.get('/api/goals')
def get_goals():
    return store.goals_state()

class GoalsVisibility(BaseModel):
    visible: bool

@app.put('/api/goals/visibility')
def goals_visibility(data: GoalsVisibility, request: Request):
    return store.set_goals_visible(data.visible, actor=_actor(request))

class GoalModel(BaseModel):
    id: str = Field(min_length=2,max_length=40)
    title: str = Field(min_length=1,max_length=90)
    metric: Literal['assigned_points','donations_usd','youtube_usd','cast_points','manual']
    target: str = Field(max_length=25)
    cast_id: str | None = None
    adjustment: str = '0'
    manual_value: str = '0'
    enabled: bool = True
    start_fresh: bool = True
    reset_baseline: bool = False
    ends_at: str | None = None
    ticker: str = Field(default='', max_length=160)
    sort_order: int = Field(default=0,ge=0,le=10000)

@app.post('/api/goals')
def create_goal(goal: GoalModel, request: Request):
    try:
        return store.upsert_goal(goal.model_dump(), actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.put('/api/goals/{goal_id}')
def edit_goal(goal_id: str, goal: GoalModel, request: Request):
    if goal_id != goal.id:
        raise HTTPException(400,'Goal ID cannot be changed; create a new goal')
    try:
        return store.upsert_goal(goal.model_dump(), updating=True, actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.delete('/api/goals/{goal_id}')
def remove_goal(goal_id: str, request: Request):
    try:
        return store.delete_goal(goal_id, actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.get('/api/donations')
def list_donations(status: Literal['pending','assigned','all']='pending',q: str='',
                   limit: int=50, offset: int=0,
                   source: Literal['all','youtube','simulation']='all'):
    try:
        return store.donation_history(status, q, limit, offset, source)
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.get('/api/data/summary')
def data_summary():
    return store.cast_summary()

@app.get('/api/data/history')
def full_history(status: Literal['all','assigned','pending']='all',
                 source: Literal['all','youtube','simulation']='all', cast_id: str='all',
                 q: str='',limit: int=50,offset: int=0):
    try:return store.operator_history(status,q,limit,offset,source,cast_id)
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.get('/api/data/transaction/{transaction_id:path}')
def transaction(transaction_id: str):
    try:return store.transaction_detail(transaction_id)
    except ValueError as exc:raise HTTPException(404,str(exc))

class TransactionCorrection(BaseModel):
    cast_id: str | None = None
    amount: str = Field(min_length=1,max_length=30)
    reason: str = Field(min_length=8,max_length=500)

@app.put('/api/data/transaction/{transaction_id:path}')
def update_transaction(transaction_id: str,data: TransactionCorrection,request: Request):
    try:return store.correct_transaction(transaction_id,data.cast_id,data.amount,data.reason,actor=getattr(request.state,'operator_identity',{}).get('username','operator'))
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.get('/api/debug/events')
def debug_events(limit: int=50,offset:int=0):
    try:return store.test_event_history(limit,offset)
    except ValueError as exc:raise HTTPException(400,str(exc))

class RemoveTestEvents(BaseModel):
    ids: list[str] = Field(min_length=1,max_length=500)
    reason: str = Field(min_length=8,max_length=500)

@app.post('/api/debug/remove')
def debug_remove(data: RemoveTestEvents,request: Request):
    try:return store.remove_test_events(data.ids,data.reason,actor=getattr(request.state,'operator_identity',{}).get('username','operator'))
    except ValueError as exc:raise HTTPException(400,str(exc))

class ClearTestEvents(BaseModel):
    confirm: Literal['CLEAR TEST EVENTS']
    reason: str = Field(min_length=8,max_length=500)

@app.post('/api/debug/clear')
def debug_clear(data: ClearTestEvents,request: Request):
    try:return store.clear_test_events(data.reason,actor=getattr(request.state,'operator_identity',{}).get('username','operator'))
    except ValueError as exc:raise HTTPException(400,str(exc))

class TestBurst(BaseModel):
    count: int = Field(ge=1,le=100)
    cast_id: str = Field(min_length=2,max_length=40)

@app.post('/api/debug/burst')
def debug_burst(data: TestBurst, request: Request):
    if data.cast_id not in {m['id'] for m in store.state()['cast']}:
        raise HTTPException(400,'Unknown cast member')
    created=0
    target=next(m for m in store.state()['cast'] if m['id']==data.cast_id)
    tag=target['hashtags'][0] if target['hashtags'] else target['name'].split()[0]
    for i in range(data.count):
        event={'id':'simulation-burst-'+uuid.uuid4().hex,
               'snippet':{'type':'superChatEvent','publishedAt':datetime.now(timezone.utc).isoformat(),
                  'superChatDetails':{'amountMicros':'1000000','currency':'USD',
                       'amountDisplayString':'$1.00','userComment':'Debug test #'+tag}},
               'authorDetails':{'displayName':'Debug Burst'}}
        # Explicitly assigned by the controlled test generator; never on-air in production.
        result=store.ingest(event,source='simulation',actor=_actor(request))
        if result['result']=='created':created+=1
    return {'created':created,'requested':data.count,'source':'simulation'}

@app.get('/api/youtube/status')
def youtube_status():
    return youtube_monitor.snapshot()


class YouTubeConfig(BaseModel):
    video: str = Field(default='', max_length=250)
    enabled: bool = False


@app.put('/api/youtube/config')
async def youtube_set_config(data: YouTubeConfig, request: Request):
    try:
        video_id = video_id_from_input(data.video) if data.video.strip() else ''
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if data.enabled and not video_id:
        raise HTTPException(400, 'Enter a valid live YouTube video URL before enabling')
    if data.enabled and not youtube_monitor.api_key:
        raise HTTPException(400, 'Add YOUTUBE_API_KEY in Render Environment first')
    previous = youtube_monitor.config()
    saved = store.set_youtube_config(video_id, data.enabled, actor=_actor(request))
    if saved != previous:
        youtube_monitor.configuration_changed()
    return saved


@app.get('/api/state')
def state():
    return {**store.state(), 'broadcast_queue_enabled': store.QUEUE_MODE}

@app.get('/api/alerts')
def alerts(after: int = 0, limit: int = 100, check_after: int | None = None):
    data = {'alerts':store.alerts(max(0, after), limit)}
    if check_after is not None:
        data['cancelled'] = store.cancelled_alerts(max(0, check_after))
    return data

class TestDonation(BaseModel):
    amount: str = Field(default='20.00', max_length=30)
    message: str = Field(default='#Marcus', max_length=500)
    donor: str = Field(default='Test Viewer', max_length=100)
    kind: Literal['superChatEvent','superStickerEvent','textMessageEvent'] = 'superChatEvent'
    currency: Literal['USD','EUR','CAD','HTG'] = 'USD'
    event_id: str | None = Field(default=None, max_length=100)

@app.post('/api/simulate')
def simulate(data: TestDonation, request: Request):
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
    event_id = (data.event_id or '').strip() or f'simulation-{uuid.uuid4().hex}'
    if event_id.startswith('yt:'):
        raise HTTPException(400, 'The yt: prefix is reserved for YouTube donations')
    try:
        result = store.ingest({'id':event_id, 'snippet':snippet,
                               'authorDetails':{'displayName':data.donor}}, actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return result

class Assignment(BaseModel):
    donation_id: str = Field(min_length=1, max_length=153)
    cast_id: str = Field(min_length=1, max_length=50)
    reason: str = Field(default='Producer review', min_length=3, max_length=250)

@app.post('/api/assign')
def assign(data: Assignment,request: Request):
    try:
        return store.assign(data.donation_id, data.cast_id, data.reason,actor=getattr(request.state,'operator_identity',{}).get('username','operator'))
    except ValueError as exc:
        raise HTTPException(400,str(exc))

class ScoreSettings(BaseModel):
    points_per_usd: str = Field(max_length=25)

@app.put('/api/settings')
def change_settings(data: ScoreSettings, request: Request):
    try:
        store.set_multiplier(data.points_per_usd, actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    return {'ok':True,'points_per_usd':store.state()['points_per_usd']}

class Member(BaseModel):
    id: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    hashtags: list[str] = Field(min_length=1, max_length=15)
    active: bool = True

@app.post('/api/cast')
def update_cast(data: Member, request: Request):
    try:
        return store.cast_upsert(data.model_dump(), actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.get('/api/graphics')
def get_graphics():
    return {'graphics':[{**g,'public_url':ops.PAGES_BASE+'pages-overlay.html?graphic='+g['id']} for g in store.get_graphics()]}

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
def edit_graphic(graphic_id: str, data: GraphicDraft,request: Request):
    try:
        return store.draft_graphic(graphic_id,data.model_dump(),actor=getattr(request.state,'operator_identity',{}).get('username','operator'))
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.post('/api/graphics/{graphic_id}/publish')
def publish_graphic(graphic_id: str,request: Request):
    try:
        return store.publish_graphic(graphic_id,actor=getattr(request.state,'operator_identity',{}).get('username','operator'))
    except ValueError as exc:
        raise HTTPException(400,str(exc))

class NewGraphic(BaseModel):
    source_id: str
    id: str
    name: str = Field(min_length=1,max_length=70)

@app.post('/api/graphics')
def clone_graphic(data: NewGraphic,request: Request):
    try:
        return store.clone_graphic(data.source_id,data.id,data.name,actor=getattr(request.state,'operator_identity',{}).get('username','operator'))
    except ValueError as exc:
        raise HTTPException(400,str(exc))

@app.get('/api/export/donations.csv')
def export_donations():
    rows = store.export_rows()
    output = io.StringIO()
    names = ['id','kind','donor','message','amount_micros','currency','amount_display',
             'cast_id','status','points_milli','published_at','received_at','source','adjusted_amount_micros','original_points_milli']
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
def reset(data: Reset, request: Request):
    if data.confirm != 'RESET DEMO':
        raise HTTPException(400, 'Confirmation must be RESET DEMO')
    if store.LIVE_MODE:
        raise HTTPException(403,'Destructive reset is disabled in production')
    result=store.clear_test_events('Staging test data reset requested',actor=_actor(request))
    return {'ok':True,**result}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000, workers=1)
