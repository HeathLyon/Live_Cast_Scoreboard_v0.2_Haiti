"""Control room permissions, transaction corrections, and synthetic event cleanup."""
import json
import hashlib
import os
import secrets
import store
import app as service
from fastapi.testclient import TestClient


def paid(event_id, amount=10, tag='#Marcus', donor='Test Viewer'):
    return {'id':event_id,'snippet':{'type':'superChatEvent','publishedAt':'2026-11-20T12:00:00Z',
              'superChatDetails':{'amountMicros':str(amount*1_000_000),'currency':'USD',
                        'amountDisplayString':f'${amount}','userComment':tag}},
            'authorDetails':{'displayName':donor}}


def test_history_filters_corrected_amount_preserves_original(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'history.sqlite3')
    monkeypatch.setattr(store,'LIVE_MODE',True)
    monkeypatch.setattr(store,'QUEUE_MODE',True)
    store.initialize()
    store.ingest(paid('yt:correct-me'),source='youtube')
    store.ingest(paid('simulation-one',5),source='simulation')
    assert store.operator_history(source='youtube')['total']==1
    assert store.operator_history(cast_id='marcus')['total']==2
    before=store.state()['ranking']
    assert before[0]['points']=='10.00'
    result=store.correct_transaction('yt:correct-me','avery','20.00','Verified amount and cast on YouTube','producer_a')
    assert result['result']=='updated'
    assert store.state()['ranking'][0]['name']=='Avery'
    assert store.state()['ranking'][0]['points']=='20.00'
    detail=store.transaction_detail('yt:correct-me')
    assert detail['item']['amount_micros']==10_000_000
    assert detail['item']['effective_amount_micros']==20_000_000
    assert detail['audit'][0]['action']=='transaction_correction'
    assert json.loads(detail['audit'][0]['details'])['actor']=='producer_a'
    assert store.broadcast_status()['skipped']==1
    # Independent second correction derives original scoring rate, not prior rounded value.
    store.correct_transaction('yt:correct-me','avery','30.00','Follow-up reconciliation','producer_a')
    assert store.state()['ranking'][0]['points']=='30.00'
    assert store.operator_history(cast_id='avery')['total']==1
    assert store.operator_history(cast_id='marcus')['total']==1


def test_test_cleanup_does_not_remove_real_donations(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'debug.sqlite3')
    monkeypatch.setattr(store,'LIVE_MODE',True)
    monkeypatch.setattr(store,'QUEUE_MODE',True)
    store.initialize()
    store.ingest(paid('yt:real'),source='youtube')
    for i in range(3):store.ingest(paid(f'sim:{i}'),source='simulation')
    try:
        store.remove_test_events(['yt:real'],'Unwanted change','admin')
        assert False, 'Real transactions must be protected'
    except ValueError:pass
    assert store.remove_test_events(['sim:0'],'Delete a synthetic event','admin')['removed']==1
    assert store.test_event_history()['total']==2
    assert store.clear_test_events('End of testing session','admin')['removed']==2
    assert store.test_event_history()['total']==0
    assert store.operator_history(source='youtube')['total']==1
    assert store.state()['ranking'][0]['points']=='10.00'


def test_named_user_role_limits_and_private_route(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'access.sqlite3')
    monkeypatch.setattr(service,'REMOTE_TEST',True)
    monkeypatch.setattr(service,'PUBLIC_OVERLAYS',True)
    monkeypatch.setattr(service,'OPERATOR_PASSWORD','staging-operator-secure')
    monkeypatch.setattr(service,'VIEW_TOKEN','viewer-token-does-not-allow-operator-actions-123')
    salt=secrets.token_bytes(16)
    def hashed(password):return 'scrypt$16384$8$1$'+salt.hex()+'$'+hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex()
    users={'chief':{'role':'admin','password_hash':hashed('super-strong-admin-password')},
           'floor':{'role':'producer','password_hash':hashed('super-strong-producer-password')},
           'guest':{'role':'viewer','password_hash':hashed('super-strong-viewer-password')}}
    monkeypatch.setenv('LIVECAST_USERS_JSON',json.dumps(users))
    with TestClient(service.app) as client:
        admin=('chief','super-strong-admin-password')
        producer=('floor','super-strong-producer-password')
        viewer=('guest','super-strong-viewer-password')
        assert client.get('/api/data/history').status_code==401
        assert client.get('/api/data/history',auth=viewer).status_code==200
        assert client.get('/api/debug/events',auth=producer).status_code==403
        assert client.post('/api/simulate',auth=producer,json={'message':'#Marcus'}).status_code==403
        assert client.post('/api/debug/burst',auth=admin,json={'count':5,'cast_id':'marcus'}).status_code==200
        assert client.get('/api/debug/events',auth=admin).json()['total']==5
        id = client.get('/api/debug/events', auth=admin).json()['items'][0]['id']
        correction = {'amount':'20','cast_id':'avery','reason':'Verified correction'}
        assert client.put('/api/data/transaction/'+id,auth=producer,json=correction).status_code==200
        detail = client.get('/api/data/transaction/'+id, auth=producer).json()
        assert json.loads(detail['audit'][0]['details'])['actor'] == 'floor'
        assert client.post('/api/graphics/top3/publish',auth=producer).status_code==200
        assert client.post('/api/graphics/top3/publish',auth=viewer).status_code==403
        assert client.post('/api/debug/clear',auth=viewer,json={'confirm':'CLEAR TEST EVENTS','reason':'End of the session'}).status_code==403
        assert client.get('/api/system/backup.sqlite3',auth=producer).status_code==403
        assert client.get('/api/system/status',auth=producer).json()['operator']['username']=='floor'
        assert client.get('/public/state').status_code==200
        assert client.put('/api/data/transaction/simulation-bad',auth=viewer,json={'amount':'20','cast_id':'marcus','reason':'Verified correction'}).status_code==403
        assert client.post('/api/debug/clear',auth=admin,json={'confirm':'CLEAR TEST EVENTS','reason':'End of the session'}).json()['removed']==5


def test_correction_invalidates_alert_for_staging_and_grouped_playback(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DB_PATH', tmp_path / 'cancel.sqlite3')
    monkeypatch.setattr(store, 'QUEUE_MODE', True)
    monkeypatch.setattr(store, 'GROUP_THRESHOLD', 2)
    monkeypatch.setattr(service, 'PUBLIC_OVERLAYS', True)
    store.initialize()
    store.ingest(paid('yt:first'), source='youtube')
    store.ingest(paid('yt:second'), source='youtube')
    sequences = [event['seq'] for event in store.alerts(0)]
    store.control_broadcast('group_on')
    store.advance_broadcast()
    assert store.broadcast_status()['active']['kind'] == 'summary'
    store.correct_transaction('yt:second', 'avery', '20.00', 'Verified grouped donation')
    assert store.broadcast_status()['active'] is None
    assert store.state()['last_alert_id'] == sequences[1]
    with TestClient(service.app) as client:
        feed = client.get('/public/alerts', params={'after': 0, 'check_after': 0}).json()
        assert [event['seq'] for event in feed['alerts']] == sequences[:1]
        assert feed['cancelled'] == sequences[1:]


def test_graphic_url_and_html_wiring(tmp_path,monkeypatch):
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    html=(root/'index.html').read_text()
    assert 'id="tab-data"' in html and 'id="debug-list"' in html
    assert 'js/controlroom.js' in html and 'id="graphic-url"' in html
    assert 'document.getElementById' in (root/'js/controlroom.js').read_text() or "const $=id=>document.getElementById(id)" in (root/'js/controlroom.js').read_text()
