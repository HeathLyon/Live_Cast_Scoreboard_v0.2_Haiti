"""GitHub Pages uses a narrowly-scoped public, read-only API."""
from pathlib import Path
from fastapi.testclient import TestClient
import app as app_module
import store


def test_public_broadcast_and_operator_security(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DB_PATH', tmp_path/'pages_test.sqlite3')
    monkeypatch.setattr(app_module, 'REMOTE_TEST', True)
    monkeypatch.setattr(app_module, 'PUBLIC_OVERLAYS', True)
    monkeypatch.setattr(app_module, 'OPERATOR_PASSWORD', 'a-long-example-operator-pass')
    monkeypatch.setattr(app_module, 'VIEW_TOKEN', 'a-different-secret-view-token-123')
    with TestClient(app_module.app) as client:
        origin={'Origin':'https://heathlyon.github.io'}
        state=client.get('/public/state',headers=origin)
        assert state.status_code==200
        assert state.headers.get('access-control-allow-origin')=='https://heathlyon.github.io'
        assert set(state.json()) == {'mode','revision','updated_at','last_alert_id','top3','ranking'}
        assert 'pending' not in state.json()
        assert 'hashtags' not in state.json()['ranking'][0]
        assert client.get('/public/graphics/top3').status_code==200
        assert client.get('/public/graphics/top3?preview=true').json()['title_ht']=='3 PREMYE YO'
        assert client.get('/public/alerts').json() == {'alerts':[]}
        assert client.get('/api/state').status_code==401
        assert client.get('/api/graphics').status_code==401
        assert client.post('/api/simulate',json={'message':'#Marcus'}).status_code==401
        assert client.get('/api/export/donations.csv').status_code==401
        assert client.post('/api/simulate',auth=('operator','a-long-example-operator-pass'),json={'message':'#Marcus','amount':'25.00'}).status_code==200
        snapshot=client.get('/public/state').json()
        assert snapshot['ranking'][0]['name']=='Marcus'
        assert snapshot['ranking'][0]['points']=='25.00'
        alerts=client.get('/public/alerts?after=0').json()['alerts']
        assert len(alerts)==1 and set(alerts[0])=={'seq','cast_name','delta_points','new_total','rank'}
        assert alerts[0]['delta_points']=='25.00'
        # Unapproved domains cannot read public API responses via browser CORS.
        bad=client.get('/public/state',headers={'Origin':'https://evil.example'})
        assert bad.status_code==200 and 'access-control-allow-origin' not in bad.headers


def test_public_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'private.sqlite3')
    monkeypatch.setattr(app_module,'REMOTE_TEST',True)
    monkeypatch.setattr(app_module,'PUBLIC_OVERLAYS',False)
    monkeypatch.setattr(app_module,'OPERATOR_PASSWORD','a-long-example-operator-pass')
    monkeypatch.setattr(app_module,'VIEW_TOKEN','a-different-secret-view-token-123')
    with TestClient(app_module.app) as client:
        assert client.get('/public/state').status_code==401
        assert client.get('/api/state').status_code==401


def test_static_pages_asset_paths_and_readonly_feed():
    root=Path(__file__).resolve().parents[1]
    overlay=(root/'pages-overlay.html').read_text(encoding='utf-8')
    producer=(root/'pages-producer.html').read_text(encoding='utf-8')
    assert 'href="css/style.css"' in overlay
    assert 'src="js/overlay.js"' in overlay
    assert 'src="js/producer.js"' in producer
    assert "publicBackend + path.replace" in (root/'js/overlay.js').read_text(encoding='utf-8')
    assert "publicBackend+'/public/state'" in (root/'js/producer.js').read_text(encoding='utf-8')
