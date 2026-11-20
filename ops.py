"""Central deployment settings and strict single-node production preflight."""
from __future__ import annotations
import os
import json
import re
from pathlib import Path
from urllib.parse import urlparse

PROFILE = os.getenv('LIVECAST_ENV','staging').lower()
PUBLIC_BASE = os.getenv('LIVECAST_PUBLIC_URL','https://live-cast-scoreboard-demo.onrender.com').rstrip('/')
PAGES_BASE = os.getenv('LIVECAST_PAGES_URL',
                       'https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/').rstrip('/')+'/'
PASSWORD_HASH = re.compile(r'scrypt\$16384\$8\$1\$([0-9a-f]{32})\$([0-9a-f]{128})')
EPHEMERAL_ROOTS = tuple(Path(path).resolve() for path in ('/tmp', '/app', '/opt/render/project'))

def check_production_config():
    if PROFILE not in ('production','staging'):
        raise RuntimeError('LIVECAST_ENV must be staging or production')
    if PROFILE != 'production':
        return
    raw_db=os.getenv('LIVECAST_DB','')
    raw_root=os.getenv('LIVECAST_PERSISTENT_ROOT','')
    if not raw_db or not raw_root:
        raise RuntimeError('Production requires LIVECAST_DB and LIVECAST_PERSISTENT_ROOT')
    db=Path(raw_db).resolve()
    root=Path(raw_root).resolve()
    if not db.is_relative_to(root) or not root.is_dir() or not os.access(root,os.W_OK):
        raise RuntimeError('Production DB must be inside an existing writable persistent root')
    if any(root.is_relative_to(path) for path in EPHEMERAL_ROOTS):
        raise RuntimeError('Production storage root looks ephemeral')
    if os.getenv('LIVECAST_REQUIRE_MOUNT','0')=='1' and not os.path.ismount(root):
        raise RuntimeError('LIVECAST_PERSISTENT_ROOT is not a mounted volume')
    try:
        users=json.loads(os.getenv('LIVECAST_USERS_JSON',''))
        if not isinstance(users,dict) or not any(isinstance(x,dict) and x.get('role')=='admin' for x in users.values()):
            raise ValueError('At least one admin required')
        for username, item in users.items():
            if (not username or ':' in username or not isinstance(item,dict)
                or item.get('role') not in ('admin','producer','viewer')
                or not PASSWORD_HASH.fullmatch(str(item.get('password_hash','')))):
                raise ValueError('Invalid user credential')
    except (ValueError,TypeError):
        raise RuntimeError('Production requires named, hashed LIVECAST_USERS_JSON accounts including an admin')
    if len(os.getenv('VIEW_TOKEN',''))<32:
        raise RuntimeError('Production requires a strong VIEW_TOKEN')
    if os.getenv('LIVECAST_REMOTE_TEST','0')!='1':
        raise RuntimeError('Production requires LIVECAST_REMOTE_TEST=1 to authenticate operator routes')
    if not os.getenv('LIVECAST_PUBLIC_URL',''):
        raise RuntimeError('Production requires explicit LIVECAST_PUBLIC_URL')
    if not os.getenv('YOUTUBE_API_KEY',''):
        raise RuntimeError('Production requires a YouTube Data API key')
    if os.getenv('LIVECAST_SERVER_QUEUE','1')!='1':
        raise RuntimeError('Production requires server-backed broadcast queue')
    for name,url in [('LIVECAST_PUBLIC_URL',PUBLIC_BASE),('LIVECAST_PAGES_URL',PAGES_BASE)]:
        parsed=urlparse(url)
        if parsed.scheme!='https' or not parsed.hostname:
            raise RuntimeError(name+' must be an HTTPS URL')

def graphic_links():
    base=PAGES_BASE+'pages-overlay.html?graphic='
    return {'combined':base+'top3-alert', 'top3':base+'top3',
            'top3_on_donation':base+'top3&show=on-donation',
            'alert':base+'alert', 'goals':base+'goals',
            'full':base+'full', 'producer':PAGES_BASE+'pages-producer.html',
            'setup':PAGES_BASE+'pages-setup.html'}
