"""Local SQLite store for OFFLINE MVP. Do not deploy this DB to Render's ephemeral filesystem.

This layer deliberately isolates storage so a Google Sheets/transactional DB adapter can replace
it in the connected phase. SQLite provides atomic, deduplicated commits for simulation tests.
"""
from __future__ import annotations
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from core import classify_event, rank_members, format_points, validate_aliases

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv('LIVECAST_DB', str(ROOT / 'local_scoreboard.sqlite3')))
LOCK = threading.RLock()

SEED_CAST = [
    {'id': 'marcus', 'name': 'Marcus', 'hashtags': ['Marcus', 'TeamMarcus'], 'active': True},
    {'id': 'avery', 'name': 'Avery', 'hashtags': ['Avery', 'TeamAvery'], 'active': True},
    {'id': 'jordan', 'name': 'Jordan', 'hashtags': ['Jordan', 'TeamJordan'], 'active': True},
    {'id': 'taylor', 'name': 'Taylor', 'hashtags': ['Taylor', 'TeamTaylor'], 'active': True},
]
DEFAULT_GRAPHICS = [
    {'id': 'top3', 'name': 'Top Three', 'kind': 'top3', 'accent': '#d21034', 'position': 'left', 'scale': 'normal', 'title_en': 'TOP 3', 'title_ht': '3 PREMYE YO', 'duration': 6, 'enabled': True},
    {'id': 'alert', 'name': 'Donation Alert', 'kind': 'alert', 'accent': '#d21034', 'position': 'right', 'scale': 'normal', 'title_en': 'NEW SUPER CHAT', 'title_ht': 'NOUVO SUPER CHAT', 'duration': 6, 'enabled': True},
    {'id': 'full', 'name': 'Full Rankings', 'kind': 'full', 'accent': '#00209f', 'position': 'center', 'scale': 'large', 'title_en': 'LIVE CAST RANKINGS', 'title_ht': 'KLASMAN AN DIRÈK', 'duration': 6, 'enabled': True},
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=15000')
    return db


def initialize() -> None:
    with LOCK, connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS cast (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, hashtags TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS donations (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, donor TEXT NOT NULL,
          message TEXT NOT NULL, amount_micros INTEGER NOT NULL,
          currency TEXT NOT NULL, amount_display TEXT NOT NULL,
          cast_id TEXT, status TEXT NOT NULL, points_milli INTEGER NOT NULL,
          published_at TEXT NOT NULL, received_at TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'simulation'
        );
        CREATE TABLE IF NOT EXISTS alerts (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, donation_id TEXT NOT NULL,
          cast_id TEXT NOT NULL, cast_name TEXT NOT NULL, delta_points TEXT NOT NULL,
          new_total TEXT NOT NULL, rank INTEGER NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audits (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
          target TEXT NOT NULL, details TEXT NOT NULL, at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS graphics (
          id TEXT PRIMARY KEY, draft TEXT NOT NULL, published TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS goals (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, metric TEXT NOT NULL,
          target_milli INTEGER NOT NULL, baseline_milli INTEGER NOT NULL DEFAULT 0,
          adjustment_milli INTEGER NOT NULL DEFAULT 0, manual_milli INTEGER NOT NULL DEFAULT 0,
          cast_id TEXT, ends_at TEXT, ticker TEXT NOT NULL DEFAULT '',
          enabled INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        ''')
        # Upgrade existing demo databases without discarding test data.
        if 'source' not in [r['name'] for r in db.execute('PRAGMA table_info(donations)')]:
            db.execute("ALTER TABLE donations ADD COLUMN source TEXT NOT NULL DEFAULT 'simulation'")
        if db.execute('SELECT count(*) FROM cast').fetchone()[0] == 0:
            for m in SEED_CAST:
                db.execute('INSERT INTO cast VALUES (?,?,?,?)', (m['id'], m['name'], json.dumps(m['hashtags']), int(m['active'])))
        if db.execute('SELECT count(*) FROM settings').fetchone()[0] == 0:
            for key, value in [('points_per_usd','1'), ('revision','0'), ('changed_at', now()), ('goals_visible','0')]:
                db.execute('INSERT INTO settings VALUES (?,?)', (key, value))
        if _setting(db,'goals_visible') is None:
            _put_setting(db,'goals_visible','0')
        for item in DEFAULT_GRAPHICS:
            db.execute('INSERT OR IGNORE INTO graphics VALUES (?,?,?)', (item['id'], json.dumps(item), json.dumps(item)))


def _setting(db, key):
    row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return row['value'] if row else None


def _put_setting(db, key, value):
    db.execute('INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))


def _touch(db):
    _put_setting(db, 'revision', int(_setting(db,'revision') or 0) + 1)
    _put_setting(db, 'changed_at', now())


def _cast(db):
    return [dict(id=r['id'], name=r['name'], hashtags=json.loads(r['hashtags']), active=bool(r['active']))
            for r in db.execute('SELECT * FROM cast ORDER BY name COLLATE NOCASE')]


def _ranking(db):
    scores = {r['cast_id']: r['points'] for r in db.execute('''
      SELECT cast_id, SUM(points_milli) AS points FROM donations
      WHERE status='assigned' AND currency='USD' AND cast_id IS NOT NULL GROUP BY cast_id
    ''')}
    return rank_members(_cast(db), scores)


def _make_alert(db, donation: dict, ranking: list[dict]):
    member = next((m for m in ranking if m['id'] == donation['cast_id']), None)
    if not member:
        return
    db.execute('''INSERT INTO alerts (donation_id,cast_id,cast_name,delta_points,new_total,rank,created_at)
      VALUES (?,?,?,?,?,?,?)''',
      (donation['id'], member['id'], member['name'], format_points(donation['points_milli']),
       member['points'], member['rank'], now()))


def ingest(event: dict, source: str = 'simulation') -> dict:
    if source not in ('simulation', 'youtube'):
        raise ValueError('Invalid donation source')
    with LOCK, connect() as db:
        record = classify_event(event, _cast(db), _setting(db, 'points_per_usd') or '1')
        if record is None:
            return {'result':'ignored', 'reason':'not a paid event'}
        inserted = db.execute('''INSERT OR IGNORE INTO donations
          (id,kind,donor,message,amount_micros,currency,amount_display,cast_id,status,points_milli,published_at,received_at,source)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (record['id'], record['kind'], record['donor'], record['message'],record['amount_micros'],
           record['currency'],record['amount_display'],record['cast_id'],record['status'],
           record['points_milli'],record['published_at'],now(),source))
        if inserted.rowcount == 0:
            return {'result':'duplicate','id': record['id']}
        if record['status'] == 'assigned':
            _make_alert(db, record, _ranking(db))
        _touch(db)
        return {'result':'created', 'id': record['id'], 'status': record['status'],
                'source': source, 'cast_id':record['cast_id'], 'points':format_points(record['points_milli'])}


def assign(donation_id: str, cast_id: str, reason: str) -> dict:
    with LOCK, connect() as db:
        m = next((m for m in _cast(db) if m['id'] == cast_id and m['active']), None)
        if not m:
            raise ValueError('Unknown or inactive cast member')
        old = db.execute('SELECT * FROM donations WHERE id=?', (donation_id,)).fetchone()
        if not old:
            raise ValueError('Donation ID not found')
        if old['currency'] != 'USD':
            raise ValueError('Non-USD events require a separate FX review policy')
        if old['status'] == 'assigned' and old['cast_id'] == cast_id:
            return {'result':'unchanged'}
        from_unassigned = old['status'] != 'assigned'
        db.execute('UPDATE donations SET cast_id=?,status=? WHERE id=?', (cast_id,'assigned', donation_id))
        db.execute('INSERT INTO audits (action,target,details,at) VALUES (?,?,?,?)',
                   ('assign', donation_id, json.dumps({'from':old['cast_id'], 'to':cast_id,
                    'reason':reason, 'previous_status':old['status']}), now()))
        if from_unassigned:
            _make_alert(db, dict(old, cast_id=cast_id, status='assigned'), _ranking(db))
        _touch(db)
        return {'result':'assigned', 'cast_id':cast_id}


def set_multiplier(multiplier: str):
    from decimal import Decimal, InvalidOperation
    try:
        value = Decimal(str(multiplier))
    except (InvalidOperation, ValueError):
        raise ValueError('Invalid multiplier')
    if not value.is_finite() or value < 0 or value > 10_000 or value.as_tuple().exponent < -3:
        raise ValueError('Multiplier must be 0–10000 with max 3 decimal places')
    with LOCK, connect() as db:
        old = _setting(db, 'points_per_usd')
        if old == str(value):
            return
        _put_setting(db, 'points_per_usd', str(value))
        db.execute('INSERT INTO audits (action,target,details,at) VALUES (?,?,?,?)',
                   ('multiplier', 'points_per_usd', json.dumps({'old':old,'new':str(value)}), now()))
        _touch(db)


def cast_upsert(member: dict):
    with LOCK, connect() as db:
        all_cast = _cast(db)
        new = {'id':member['id'].lower().strip(), 'name':member['name'].strip(),
               'hashtags':list(member['hashtags']), 'active': bool(member.get('active', True))}
        if not __import__('re').fullmatch(r'[a-z0-9_-]{2,40}', new['id']):
            raise ValueError('Cast ID must be 2–40 lowercase letters, numbers, hyphens or underscores')
        all_cast = [m for m in all_cast if m['id'] != new['id']] + [new]
        validate_aliases(all_cast)
        db.execute('INSERT INTO cast (id,name,hashtags,active) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,hashtags=excluded.hashtags,active=excluded.active',
                   (new['id'],new['name'],json.dumps(new['hashtags']), int(new['active'])))
        db.execute('INSERT INTO audits (action,target,details,at) VALUES (?,?,?,?)', ('cast_upsert',new['id'],json.dumps(new),now()))
        _touch(db)
        return new


def state() -> dict:
    with LOCK, connect() as db:
        ranking = _ranking(db)
        overview = db.execute('''SELECT COUNT(*) events,
          COALESCE(SUM(CASE WHEN currency='USD' THEN amount_micros ELSE 0 END),0) gross_usd,
          COALESCE(SUM(CASE WHEN currency='USD' AND status<>'assigned' THEN amount_micros ELSE 0 END),0) unassigned_usd,
          COALESCE(SUM(CASE WHEN status<>'assigned' THEN 1 ELSE 0 END),0) pending,
          COALESCE(SUM(CASE WHEN source='youtube' THEN 1 ELSE 0 END),0) real_events,
          COALESCE(SUM(CASE WHEN source='simulation' THEN 1 ELSE 0 END),0) sim_events,
          COALESCE(SUM(CASE WHEN source='youtube' AND currency='USD' THEN amount_micros ELSE 0 END),0) real_usd,
          COALESCE(SUM(CASE WHEN source='simulation' AND currency='USD' THEN amount_micros ELSE 0 END),0) sim_usd
          FROM donations''').fetchone()
        pending = [dict(r) for r in db.execute('''SELECT id,kind,donor,message,amount_micros,currency,cast_id,status,received_at,source
             FROM donations WHERE status<>'assigned' ORDER BY received_at DESC,id DESC LIMIT 80''')]
        recent = [dict(r) for r in db.execute('''SELECT id,kind,donor,message,amount_micros,currency,cast_id,status,received_at,source
            FROM donations ORDER BY received_at DESC,id DESC LIMIT 20''')]
        alert_sequence = db.execute("SELECT seq FROM sqlite_sequence WHERE name='alerts'").fetchone()
        max_alert = alert_sequence['seq'] if alert_sequence else 0
        return {'mode':'DEMO — LIVE + SIMULATED EVENTS MIXED', 'revision':int(_setting(db,'revision') or 0),
                'updated_at': _setting(db,'changed_at'),
                'points_per_usd':_setting(db,'points_per_usd'),
                'cast':_cast(db), 'ranking':ranking,'top3':ranking[:3],
                'event_count':overview['events'], 'gross_usd':format_points(overview['gross_usd'] // 1000),
                'youtube_event_count': overview['real_events'], 'simulated_event_count': overview['sim_events'],
                'youtube_gross_usd': format_points(overview['real_usd'] // 1000),
                'simulated_gross_usd': format_points(overview['sim_usd'] // 1000),
                'unassigned_usd':format_points(overview['unassigned_usd'] // 1000),
                'pending_count':overview['pending'], 'pending':pending, 'recent':recent,
                'last_alert_id':max_alert}



def youtube_config(default_video_id: str = '', default_enabled: bool = False) -> dict:
    with LOCK, connect() as db:
        video = _setting(db, 'youtube_video_id')
        enabled = _setting(db, 'youtube_enabled')
        return {'video_id': video if video is not None else default_video_id,
                'enabled': (enabled == '1') if enabled is not None else bool(default_enabled)}


def set_youtube_config(video_id: str, enabled: bool) -> dict:
    with LOCK, connect() as db:
        _put_setting(db, 'youtube_video_id', video_id)
        _put_setting(db, 'youtube_enabled', '1' if enabled else '0')
        db.execute('INSERT INTO audits (action,target,details,at) VALUES (?,?,?,?)',
                   ('youtube_config', 'youtube', json.dumps({'video_id':video_id,'enabled':enabled}), now()))
    return {'video_id': video_id, 'enabled': bool(enabled)}


def alerts(after: int, limit: int = 100):
    with LOCK, connect() as db:
        return [dict(r) for r in db.execute('''SELECT * FROM alerts WHERE seq>? ORDER BY seq LIMIT ?''',
                     (after, min(max(limit,1),200)))]


def get_graphics():
    with LOCK, connect() as db:
        return [dict(id=r['id'], draft=json.loads(r['draft']), published=json.loads(r['published']))
                for r in db.execute('SELECT * FROM graphics ORDER BY id')]


def get_graphic(graphic_id, preview: bool = False):
    with LOCK, connect() as db:
        r = db.execute('SELECT draft,published FROM graphics WHERE id=?', (graphic_id,)).fetchone()
        return json.loads(r['draft' if preview else 'published']) if r else None


def draft_graphic(graphic_id: str, values: dict):
    with LOCK, connect() as db:
        old = get_graphic(graphic_id, preview=True)
        if not old:
            raise ValueError('Unknown graphic')
        safe = {k:values[k] for k in ('name','accent','position','scale','title_en','title_ht','duration','enabled') if k in values}
        new = {**old, **safe}
        if not __import__('re').fullmatch(r'#[0-9a-fA-F]{6}', str(new['accent'])):
            raise ValueError('Accent must be a 6-digit hex color')
        if new['position'] not in ('left','center','right') or new['scale'] not in ('small','normal','large'):
            raise ValueError('Invalid graphic position/scale')
        if not 2 <= int(new['duration']) <= 20:
            raise ValueError('Duration must be 2–20 seconds')
        new['duration'] = int(new['duration'])
        for key in ['name','title_en','title_ht']:
            new[key] = str(new[key])[:70]
        new['enabled'] = bool(new['enabled'])
        db.execute('UPDATE graphics SET draft=? WHERE id=?', (json.dumps(new), graphic_id))
        return new


def publish_graphic(graphic_id: str):
    with LOCK, connect() as db:
        preview = get_graphic(graphic_id, preview=True)
        if not preview:
            raise ValueError('Unknown graphic')
        db.execute('UPDATE graphics SET published=? WHERE id=?', (json.dumps(preview), graphic_id))
        db.execute('INSERT INTO audits (action,target,details,at) VALUES (?,?,?,?)',
                   ('graphic_publish',graphic_id,json.dumps(preview),now()))
        _touch(db)
        return preview


def clone_graphic(source_id: str, new_id: str, new_name: str):
    if new_id in ('goals', 'top3-alert'):
        raise ValueError('That graphic ID is reserved')
    with LOCK, connect() as db:
        source = get_graphic(source_id)
        if not source:
            raise ValueError('Unknown source graphic')
        if not __import__('re').fullmatch(r'[a-z0-9-]{3,36}', new_id):
            raise ValueError('Use a URL ID with 3–36 lowercase letters, digits or hyphens')
        new = dict(source, id=new_id, name=new_name[:70])
        try:
            db.execute('INSERT INTO graphics (id,draft,published) VALUES (?,?,?)',
                       (new_id,json.dumps(new),json.dumps(new)))
        except sqlite3.IntegrityError:
            raise ValueError('That graphic ID already exists')
        _touch(db)
        return new



# Goal values are stored as integer thousandths, matching scoreboard point precision.
GOAL_METRICS = ('assigned_points','donations_usd','youtube_usd','cast_points','manual')


def _milli(value, field='Amount', allow_negative=False) -> int:
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(field+' must be a number')
    if (not decimal.is_finite() or abs(decimal) > Decimal('1000000000')
            or decimal.as_tuple().exponent < -3 or (not allow_negative and decimal < 0)):
        raise ValueError(field+' must be a valid amount (up to 3 decimal places)')
    return int((decimal * 1000).to_integral_value(rounding=ROUND_HALF_UP))


def _metric_milli(db, metric: str, cast_id: str | None = None) -> int:
    if metric == 'manual':
        return 0
    if metric == 'assigned_points':
        row = db.execute("SELECT COALESCE(SUM(points_milli),0) v FROM donations WHERE status='assigned' AND currency='USD'").fetchone()
    elif metric == 'cast_points':
        row = db.execute("SELECT COALESCE(SUM(points_milli),0) v FROM donations WHERE status='assigned' AND currency='USD' AND cast_id=?", (cast_id,)).fetchone()
    elif metric == 'youtube_usd':
        row = db.execute("SELECT COALESCE(SUM(amount_micros),0)/1000 v FROM donations WHERE currency='USD' AND source='youtube'").fetchone()
    elif metric == 'donations_usd':
        row = db.execute("SELECT COALESCE(SUM(amount_micros),0)/1000 v FROM donations WHERE currency='USD'").fetchone()
    else:
        raise ValueError('Unknown goal metric')
    return int(row['v'] or 0)


def _goal_view(db, row) -> dict:
    g = dict(row)
    underlying = _metric_milli(db, g['metric'], g['cast_id'])
    current = (g['manual_milli'] if g['metric']=='manual' else
               underlying - g['baseline_milli'] + g['adjustment_milli'])
    current = max(0, current)
    target = g['target_milli']
    return {
        'id':g['id'], 'title':g['title'], 'metric':g['metric'], 'cast_id':g['cast_id'],
        'target': format_points(target), 'current':format_points(current),
        'percent':round(min(100, 100 * current / target), 1),
        'complete':current >= target,
        'baseline':format_points(g['baseline_milli']),
        'adjustment':format_points(g['adjustment_milli']),
        'manual_value':format_points(g['manual_milli']),
        'ends_at':g['ends_at'], 'ticker':g['ticker'], 'enabled':bool(g['enabled']),
        'sort_order':g['sort_order'], 'created_at':g['created_at'], 'updated_at':g['updated_at']
    }


def goals_state(public: bool=False) -> dict:
    with LOCK, connect() as db:
        visible = _setting(db,'goals_visible') == '1'
        rows = db.execute('SELECT * FROM goals ORDER BY sort_order,created_at,id').fetchall()
        goals = [_goal_view(db, r) for r in rows]
        if public:
            goals = [{k:g[k] for k in ('id','title','metric','current','target',
                        'percent','complete','ends_at','ticker','enabled')}
                     for g in goals if g['enabled']] if visible else []
        return {'visible':visible,'goals':goals}


def set_goals_visible(visible: bool) -> dict:
    with LOCK, connect() as db:
        _put_setting(db,'goals_visible', '1' if visible else '0')
        db.execute('INSERT INTO audits (action,target,details,at) VALUES (?,?,?,?)',
                   ('goals_visibility','all',json.dumps({'visible':visible}),now()))
        _touch(db)
    return goals_state()


def upsert_goal(goal: dict, updating: bool=False) -> dict:
    import re
    goal_id = goal['id']
    if not re.fullmatch('[a-z0-9-]{2,40}', goal_id):
        raise ValueError('Goal ID must be 2–40 lowercase letters, numbers or hyphens')
    metric=goal['metric']
    if metric not in GOAL_METRICS:
        raise ValueError('Unknown goal metric')
    title = goal['title'].strip()
    if not title or len(title)>90:
        raise ValueError('Goal title must be 1–90 characters')
    target=_milli(goal['target'],'Goal target')
    if target <= 0:
        raise ValueError('Goal target must be greater than zero')
    manual=_milli(goal.get('manual_value','0'),'Manual count')
    adjustment=_milli(goal.get('adjustment','0'),'Adjustment', allow_negative=True)
    cast_id=goal.get('cast_id') or None
    ticker=(goal.get('ticker') or '').strip()
    if len(ticker)>160:
        raise ValueError('Ticker must be 160 characters or fewer')
    ends_at=goal.get('ends_at') or None
    if ends_at:
        try:
            date=datetime.fromisoformat(ends_at.replace('Z','+00:00'))
            if date.tzinfo is None: raise ValueError()
            ends_at=date.astimezone(timezone.utc).isoformat()
        except ValueError:
            raise ValueError('Countdown must be an ISO date with a timezone')
    with LOCK, connect() as db:
        old=db.execute('SELECT * FROM goals WHERE id=?',(goal_id,)).fetchone()
        if bool(old) != updating:
            raise ValueError('Goal already exists' if old else 'Goal does not exist')
        if metric=='cast_points' and not any(m['id']==cast_id for m in _cast(db)):
            raise ValueError('Choose an existing cast member for cast points')
        reset=bool(goal.get('reset_baseline',False))
        baseline = (_metric_milli(db,metric,cast_id) if goal.get('start_fresh',True) else 0) if not old else (
            _metric_milli(db,metric,cast_id) if reset or metric!=old['metric'] or cast_id!=old['cast_id'] else old['baseline_milli'])
        order=int(goal.get('sort_order',0))
        if order < 0 or order > 10000: raise ValueError('Sort order must be 0–10000')
        stamp=now()
        db.execute('''INSERT INTO goals
          (id,title,metric,target_milli,baseline_milli,adjustment_milli,manual_milli,
           cast_id,ends_at,ticker,enabled,sort_order,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET title=excluded.title,metric=excluded.metric,
          target_milli=excluded.target_milli,baseline_milli=excluded.baseline_milli,
          adjustment_milli=excluded.adjustment_milli,manual_milli=excluded.manual_milli,
          cast_id=excluded.cast_id,ends_at=excluded.ends_at,ticker=excluded.ticker,
          enabled=excluded.enabled,sort_order=excluded.sort_order,updated_at=excluded.updated_at''',
          (goal_id,title,metric,target,baseline,adjustment,manual,cast_id,ends_at,ticker,
           int(goal.get('enabled',True)),order,old['created_at'] if old else stamp,stamp))
        db.execute('INSERT INTO audits (action,target,details,at) VALUES (?,?,?,?)',
                   ('goal_update' if updating else 'goal_create',goal_id,
                    json.dumps({'title':title,'metric':metric,'target':goal['target'],'enabled':goal.get('enabled',True)}),stamp))
        _touch(db)
        saved=db.execute('SELECT * FROM goals WHERE id=?',(goal_id,)).fetchone()
        return _goal_view(db,saved)


def delete_goal(goal_id: str):
    with LOCK, connect() as db:
        if not db.execute('SELECT 1 FROM goals WHERE id=?',(goal_id,)).fetchone():
            raise ValueError('Unknown goal')
        db.execute('DELETE FROM goals WHERE id=?',(goal_id,))
        db.execute('INSERT INTO audits (action,target,details,at) VALUES (?,?,?,?)',
                   ('goal_delete',goal_id,'{}',now()))
        _touch(db)
    return {'ok':True}


def donation_history(status='pending', search='', limit=50, offset=0, source='all') -> dict:
    if status not in ('pending','assigned','all'):
        raise ValueError('Invalid donation filter')
    if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
        raise ValueError('Invalid pagination')
    with LOCK,connect() as db:
        clauses=[]; params=[]
        if status!='all':
            clauses.append("status<> 'assigned'" if status=='pending' else "status='assigned'")
        if source != 'all':
            clauses.append('source=?')
            params.append(source)
        if search:
            pattern = '%' + search[:100].replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
            clauses.append("(id LIKE ? ESCAPE '!' OR donor LIKE ? ESCAPE '!' OR message LIKE ? ESCAPE '!')")
            params.extend([pattern]*3)
        where=' WHERE '+ ' AND '.join(clauses) if clauses else ''
        total=db.execute('SELECT COUNT(*) FROM donations'+where,params).fetchone()[0]
        rows=[dict(r) for r in db.execute('''SELECT id,kind,donor,message,amount_micros,currency,
                     cast_id,status,received_at,published_at,source
                     FROM donations'''+where+' ORDER BY received_at DESC,id DESC LIMIT ? OFFSET ?',params+[limit,offset])]
        return {'total':total,'items':rows,'limit':limit,'offset':offset}


def export_rows():
    with LOCK, connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM donations ORDER BY received_at,id')]


def reset_simulation():
    with LOCK, connect() as db:
        db.execute("DELETE FROM alerts WHERE donation_id IN (SELECT id FROM donations WHERE source='simulation')")
        db.execute("DELETE FROM donations WHERE source='simulation'")
        db.execute('INSERT INTO audits (action,target,details,at) VALUES (?,?,?,?)',
                   ('reset_simulation','simulation','{}',now()))
        _touch(db)
