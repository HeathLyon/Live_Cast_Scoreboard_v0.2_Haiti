"""Release-candidate regression: real-only accounting, queue and access boundaries."""
from pathlib import Path
import json
import os
import sqlite3
import tempfile
import pytest
from fastapi.testclient import TestClient
import store
import app as app_module
import ops


def event(id,comment='#Marcus',amount=10):
    return {'id':id,'snippet':{'type':'superChatEvent','publishedAt':'2026-11-19T23:00:00Z',
            'superChatDetails':{'amountMicros':str(amount*1000000),'currency':'USD',
                                'amountDisplayString':'$'+str(amount),'userComment':comment}},
            'authorDetails':{'displayName':'Unit Test'}}


def test_production_live_and_test_lanes_never_mix(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'prod.sqlite3')
    monkeypatch.setattr(store,'LIVE_MODE',True)
    monkeypatch.setattr(store,'QUEUE_MODE',True)
    store.initialize()
    assert store.ingest(event('test-a'),source='simulation')['result']=='created'
    assert store.state()['simulated_event_count']==1
    assert store.state()['event_count']==0
    assert store.state()['last_alert_id']==0
    assert store.alerts(0)==[]
    assert store.broadcast_status()['pending']==0
    assert store.ingest(event('yt:a',amount=20),source='youtube')['result']=='created'
    assert store.ingest(event('yt:a',amount=20),source='youtube')['result']=='duplicate'
    state=store.state()
    assert state['event_count']==1 and state['gross_usd']=='20.00'
    assert state['ranking'][0]['points']=='20.00'
    assert state['simulated_event_count']==1 and state['youtube_event_count']==1
    assert state['last_alert_id']>0
    assert store.broadcast_status()['pending']==1
    assert len(store.alerts(0))==1
    assert store.ingest(event('test-review',comment='no tag'),source='simulation')['status']=='review'
    store.assign('test-review','marcus','Producer verification')
    assert store.state()['ranking'][0]['points']=='20.00'
    assert store.broadcast_status()['pending']==1
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM donations').fetchone()[0]==3


def test_queue_resume_skip_and_restart(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'queue.sqlite3')
    monkeypatch.setattr(store,'LIVE_MODE',True)
    monkeypatch.setattr(store,'QUEUE_MODE',True)
    store.initialize()
    for i in range(3):
        assert store.ingest(event(f'yt:{i}',amount=i+1),source='youtube')['result']=='created'
    assert store.broadcast_status()['paused'] is True
    store.advance_broadcast()
    assert store.broadcast_status()['active'] is None
    store.control_broadcast('resume');store.advance_broadcast()
    on_air=store.broadcast_status()
    assert on_air['active']['id']==1
    assert on_air['pending']==2
    store.control_broadcast('skip');store.advance_broadcast()
    next_one=store.broadcast_status()
    assert next_one['skipped']==1 and next_one['active']['id']==2
    # Simulate completion without sleeping 6 seconds.
    with store.connect() as db:
        db.execute("UPDATE broadcast_queue SET ends_at='2020-01-01T00:00:00+00:00' WHERE id=2")
    store.advance_broadcast()
    assert store.broadcast_status()['active']['id']==3
    # The active queue item survives across a client/browser refresh.
    assert store.broadcast_status()['active']['id']==3


def test_production_strict_preflight_requires_persistent_volume(monkeypatch,tmp_path):
    monkeypatch.setattr(ops,'PROFILE','production')
    ephemeral = tmp_path / 'ephemeral'
    ephemeral.mkdir()
    monkeypatch.setattr(ops, 'EPHEMERAL_ROOTS', (ephemeral,))
    monkeypatch.setenv('LIVECAST_DB', str(ephemeral / 'never-production.sqlite3'))
    monkeypatch.setenv('LIVECAST_PERSISTENT_ROOT', str(ephemeral))
    monkeypatch.setenv('LIVECAST_REMOTE_TEST','1')
    monkeypatch.setenv('OPERATOR_PASSWORD','longsecurepassword123456')
    monkeypatch.setenv('VIEW_TOKEN','longlongsecureviewertoken1234567890')
    monkeypatch.setenv('YOUTUBE_API_KEY','fake-key')
    monkeypatch.setenv('LIVECAST_PUBLIC_URL','https://paid-livecast.example.org')
    monkeypatch.setenv('LIVECAST_SERVER_QUEUE','1')
    test_hash = 'scrypt$16384$8$1$' + ('0' * 32) + '$' + ('0' * 128)
    monkeypatch.setenv('LIVECAST_USERS_JSON', json.dumps({'director': {'role': 'admin', 'password_hash': test_hash}}))
    with pytest.raises(RuntimeError, match='looks ephemeral'):
        ops.check_production_config()
    # Keep the platform-independent fixture outside paths the preflight treats as ephemeral.
    with tempfile.TemporaryDirectory(prefix='livecast-prod-test-', dir=tmp_path) as name:
        root = Path(name)
        monkeypatch.setenv('LIVECAST_DB', str(root / 'data.sqlite3'))
        monkeypatch.setenv('LIVECAST_PERSISTENT_ROOT', str(root))
        monkeypatch.setenv('LIVECAST_REQUIRE_MOUNT', '0')
        ops.check_production_config()
        monkeypatch.setenv('LIVECAST_REQUIRE_MOUNT', '1')
        with pytest.raises(RuntimeError, match='mounted volume'):
            ops.check_production_config()
        monkeypatch.setenv('LIVECAST_REQUIRE_MOUNT', '0')
        monkeypatch.delenv('LIVECAST_REMOTE_TEST')
        with pytest.raises(RuntimeError, match='authenticate operator routes'):
            ops.check_production_config()


def test_privileged_system_api_and_backup(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'secure.sqlite3')
    monkeypatch.setattr(app_module,'REMOTE_TEST',True)
    monkeypatch.setattr(app_module,'PUBLIC_OVERLAYS',True)
    monkeypatch.setattr(app_module,'OPERATOR_PASSWORD','production-test-operator-password')
    monkeypatch.setattr(app_module,'VIEW_TOKEN','a-completely-different-view-token-123456')
    with TestClient(app_module.app) as client:
        assert client.get('/api/system/status').status_code==401
        assert client.get('/api/system/backup.sqlite3').status_code==401
        assert client.post('/api/system/broadcast',json={'action':'resume'}).status_code==401
        assert client.get('/public/playback').status_code==200
        auth=('operator','production-test-operator-password')
        status=client.get('/api/system/status',auth=auth)
        assert status.status_code==200
        data=status.json()
        assert data['storage']['database_ok'] is True
        assert 'graphics' in data and 'combined' in data['graphics']
        assert 'YOUTUBE_API_KEY' not in status.text
        assert client.post('/api/system/broadcast',auth=auth,json={'action':'pause'}).status_code==200
        backup=client.get('/api/system/backup.sqlite3',auth=auth)
        assert backup.status_code==200 and backup.content.startswith(b'SQLite format 3')


def test_500_simulated_events_are_deduplicated_without_broadcasting(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'burst.sqlite3')
    monkeypatch.setattr(store,'LIVE_MODE',True)
    monkeypatch.setattr(store,'QUEUE_MODE',True)
    store.initialize()
    for i in range(500):store.ingest(event(f'test:{i}',amount=1),source='simulation')
    for i in range(500):store.ingest(event(f'test:{i}',amount=1),source='simulation')
    state=store.state()
    assert state['simulated_event_count']==500
    assert state['event_count']==0
    assert state['ranking'][0]['points']=='0.00'
    assert store.broadcast_status()['pending']==0


def test_static_pages_load_stable_public_config():
    root=Path(__file__).resolve().parents[1]
    for name in ('pages-overlay.html','pages-producer.html','pages-setup.html'):
        assert 'js/site-config.js' in (root/name).read_text(encoding='utf-8')
    assert 'window.LIVECAST_SITE' in (root/'js/site-config.js').read_text()
    assert 'top3-alert' in (root/'js/overlay.js').read_text()
    assert 'system-urls' in (root/'index.html').read_text()


def test_burst_grouping_preserves_every_real_donation(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'bursts-real.sqlite3')
    monkeypatch.setattr(store,'LIVE_MODE',True)
    monkeypatch.setattr(store,'QUEUE_MODE',True)
    store.initialize()
    for i in range(30):
        store.ingest(event(f'yt:large:{i}',amount=2),source='youtube')
    assert store.state()['event_count']==30
    assert store.state()['ranking'][0]['points']=='60.00'
    assert store.broadcast_status()['pending']==30
    store.control_broadcast('group_on')
    store.control_broadcast('resume')
    store.advance_broadcast()
    first=store.broadcast_status()
    assert first['active']['kind']=='summary'
    assert first['active']['count']==10
    assert first['active']['total_points']=='20.00'
    assert first['grouped']==9 and first['pending']==20
    # Every event is still an independent, deduplicated ledger record.
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM donations WHERE source="youtube"').fetchone()[0]==30
        assert db.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]==30
    store.control_broadcast('skip')
    store.advance_broadcast()
    second=store.broadcast_status()
    assert second['active']['kind']=='summary' and second['active']['count']==10
    assert second['grouped']==18 and second['pending']==10
    assert store.state()['ranking'][0]['points']=='60.00'
