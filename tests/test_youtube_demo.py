"""Offline integration tests for the YouTube live chat demo (no key or real stream required)."""
import asyncio
from pathlib import Path
import pytest
import httpx
from fastapi.testclient import TestClient
import app as app_module
import store
from youtube_monitor import YouTubeMonitor, normalize_paid_event, video_id_from_input


@pytest.mark.parametrize('entry', [
    'dQw4w9WgXcQ',
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'https://www.youtube.com/live/dQw4w9WgXcQ?feature=share',
    'https://youtu.be/dQw4w9WgXcQ?t=5',
])
def test_youtube_video_id_parser(entry):
    assert video_id_from_input(entry) == 'dQw4w9WgXcQ'


@pytest.mark.parametrize('entry', ['http://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://example.com/watch?v=dQw4w9WgXcQ',
        'https://www.youtube.com/watch?v=short', 'https://www.youtube.com/live/', 'not-a-video-id'])
def test_youtube_rejects_bad_video_url(entry):
    with pytest.raises(ValueError): video_id_from_input(entry)


def _chat_message(msg_id, kind='superChatEvent', currency='USD', comment='#Marcus', micros='20000000'):
    details_key='superChatDetails' if kind=='superChatEvent' else 'superStickerDetails'
    return {'id':msg_id, 'snippet':{'type':kind,
            'publishedAt':'2026-11-19T22:42:00+00:00',details_key:{'amountMicros':micros,
            'currency':currency,'userComment':comment,'amountDisplayString':'$20.00'}},
            'authorDetails':{'displayName':'Live Viewer'}}


def test_only_real_paid_message_types_enter_scoring():
    assert normalize_paid_event(_chat_message('free','textMessageEvent')) is None
    assert normalize_paid_event(_chat_message('blank', micros='0')) is None
    assert normalize_paid_event(_chat_message('bad', micros='nope')) is None
    p=normalize_paid_event(_chat_message('real-1'))
    assert p['id']=='yt:real-1'
    assert p['snippet']['superChatDetails']['userComment']=='#Marcus'
    sticker=normalize_paid_event(_chat_message('real-2',kind='superStickerEvent',comment=''))
    assert sticker['snippet']['superStickerDetails']['userComment']==''


def test_simulated_and_youtube_source_ledger_and_dedup(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'source.sqlite3')
    store.initialize()
    real=normalize_paid_event(_chat_message('abc'))
    assert store.ingest(real,source='youtube')['result']=='created'
    assert store.ingest(real,source='youtube')['result']=='duplicate'
    fake=normalize_paid_event(_chat_message('other'))
    fake['id']='simulation-123'
    assert store.ingest(fake,source='simulation')['result']=='created'
    assert store.state()['ranking'][0]['points']=='40.00'
    state=store.state()
    assert state['youtube_event_count']==1 and state['simulated_event_count']==1
    assert state['youtube_gross_usd']=='20.00' and state['simulated_gross_usd']=='20.00'
    assert {row['source'] for row in store.export_rows()} == {'simulation','youtube'}
    store.initialize()
    assert store.state()['event_count']==2


def test_non_usd_and_sticker_to_review(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'currency.sqlite3')
    store.initialize()
    foreign=store.ingest(normalize_paid_event(_chat_message('cad',currency='CAD')),source='youtube')
    sticker=store.ingest(normalize_paid_event(_chat_message('sticker',kind='superStickerEvent')),source='youtube')
    assert foreign['status']=='review_currency' and sticker['status']=='review'
    assert store.state()['gross_usd']=='20.00'
    assert store.state()['pending_count']==2
    assert store.state()['ranking'][0]['points']=='0.00'


def test_youtube_history_assignment_survives_simulation_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DB_PATH', tmp_path / 'separate-events.sqlite3')
    with TestClient(app_module.app) as client:
        donation = normalize_paid_event(_chat_message('x' * 150, comment=''))
        assert store.ingest(donation, source='youtube')['status'] == 'review'
        assert client.post('/api/simulate', json={'event_id': 'yt:reserved'}).status_code == 400
        assert client.post('/api/simulate', json={'event_id': 'test'}).status_code == 200
        items = client.get('/api/donations', params={'source': 'youtube'}).json()['items']
        assert [row['id'] for row in items] == [donation['id']]
        assert client.post('/api/assign', json={
            'donation_id': donation['id'], 'cast_id': 'marcus', 'reason': 'Historical review',
        }).status_code == 200
        assert client.post('/api/simulate', json={'event_id': 'latest-test'}).status_code == 200
        cursor = store.state()['last_alert_id']
        assert client.post('/api/reset', json={'confirm': 'RESET DEMO'}).status_code == 200
        assert store.state()['last_alert_id'] == cursor
        assert [row['donation_id'] for row in store.alerts(0)] == [donation['id']]
        assert [(row['source'], row['cast_id']) for row in store.export_rows()] == [('youtube', 'marcus')]
        assert store.state()['ranking'][0]['points'] == '20.00'


def test_youtube_operator_only_endpoints(tmp_path,monkeypatch):
    async def idle_listener(stop):
        await stop.wait()

    monkeypatch.setattr(store,'DB_PATH',tmp_path/'remote.sqlite3')
    monkeypatch.setattr(app_module,'REMOTE_TEST',True)
    monkeypatch.setattr(app_module,'PUBLIC_OVERLAYS',True)
    monkeypatch.setattr(app_module,'OPERATOR_PASSWORD','long-enough-example-operator-password')
    monkeypatch.setattr(app_module,'VIEW_TOKEN','separate-long-viewer-token-value')
    monkeypatch.setattr(app_module.youtube_monitor,'api_key','test-key-only')
    monkeypatch.setattr(app_module.youtube_monitor,'run',idle_listener)
    with TestClient(app_module.app) as client:
        assert client.get('/api/youtube/status').status_code==401
        assert client.get('/api/youtube/status',params={'view_token':'separate-long-viewer-token-value'}).status_code==401
        assert client.put('/api/youtube/config',json={'video':'dQw4w9WgXcQ','enabled':True}).status_code==401
        credential=('operator','long-enough-example-operator-password')
        assert client.get('/api/youtube/status',auth=credential).status_code==200
        assert client.put('/api/youtube/config',json={'video':'https://youtu.be/dQw4w9WgXcQ','enabled':True},auth=credential).json()=={'video_id':'dQw4w9WgXcQ','enabled':True}
        assert client.put('/api/youtube/config',json={'video':'https://evil.example/abc','enabled':True},auth=credential).status_code==400
        assert client.get('/public/state').status_code==200
        assert 'api_key_configured' not in client.get('/public/state').text
        assert 'test-key-only' not in client.get('/public/state').text
        assert client.put('/api/youtube/config',json={'video':'','enabled':False},auth=credential).status_code==200


def test_poll_live_chat_bootstrap_and_dedup(tmp_path,monkeypatch):
    return asyncio.run(_poll_live_chat_test(tmp_path,monkeypatch))


async def _poll_live_chat_test(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'poll.sqlite3')
    store.initialize()
    call_count=0
    async def handler(request):
        nonlocal call_count
        assert 'key' not in request.url.params
        assert request.headers['X-Goog-Api-Key']=='fake-key-123'
        if request.url.path.endswith('/videos'):
            return httpx.Response(200,json={'items':[{'liveStreamingDetails':{'activeLiveChatId':'LIVE_CHAT_ID'}}]})
        call_count+=1
        if call_count==1:
            return httpx.Response(200,json={'nextPageToken':'PAGE1','pollingIntervalMillis':1000,
                   'items':[_chat_message('historical')]})
        if call_count==2:
            return httpx.Response(200,json={'nextPageToken':'PAGE2','pollingIntervalMillis':2000,
                   'items':[_chat_message('fresh'),_chat_message('free',kind='textMessageEvent')]})
        return httpx.Response(200,json={'nextPageToken':'PAGE3','pollingIntervalMillis':2000,
                   'items':[_chat_message('fresh')]})
    m=YouTubeMonitor()
    m.api_key='fake-key-123';m.video_id='dQw4w9WgXcQ';m.poll_seconds=5
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await m._resolve_chat(client)
        assert await m._poll_chat(client)==5
        assert store.state()['event_count']==0  # do not replay history
        assert await m._poll_chat(client)==5
        assert store.state()['event_count']==1
        assert await m._poll_chat(client)==5
        assert m.imported==1 and m.duplicates==1
        assert store.state()['ranking'][0]['points']=='20.00'


def test_top3_syncs_with_alert_and_hides_idle_watermark():
    js=(Path(__file__).resolve().parents[1]/'js/overlay.js').read_text(encoding='utf-8')
    assert "overlayParams.get('show') === 'on-donation'" in js
    assert "graphicId === 'top3-alert'" in js
    assert 'overlayRoot.innerHTML=ranking+donation' in js
    assert 'durationMs(alertGraphic)' in js
    assert "demoWatermark.style.display" in js
    setup=(Path(__file__).resolve().parents[1]/'js/pages-setup.js').read_text(encoding='utf-8')
    assert "'top3-alert'" in setup
    assert "url.searchParams.set('show', 'on-donation')" in setup
