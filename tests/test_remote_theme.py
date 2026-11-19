"""Security boundaries for optional remote SIMULATION and flag-theme smoke checks."""
from pathlib import Path
from fastapi.testclient import TestClient
import app as app_module
import store


def test_remote_demo_requires_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DB_PATH', tmp_path/'remote.sqlite3')
    monkeypatch.setattr(app_module, 'REMOTE_TEST', True)
    monkeypatch.setattr(app_module, 'OPERATOR_PASSWORD', 'a-very-long-operator-password')
    monkeypatch.setattr(app_module, 'VIEW_TOKEN', 'a-completely-different-view-token-456')
    with TestClient(app_module.app) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/').status_code == 401
        assert client.get('/api/state').status_code == 401
        assert client.get('/overlay/top3').status_code == 401
        assert client.get('/api/graphics/top3').status_code == 401
        assert client.post('/api/simulate', json={'message':'#Marcus'}).status_code == 401
        assert client.get('/', auth=('operator','wrong')).status_code == 401
        assert client.get('/', auth=('operator','a-very-long-operator-password')).status_code == 200
        view={'view_token':'a-completely-different-view-token-456'}
        assert client.get('/producers', params=view).status_code == 200
        assert client.get('/overlay/top3', params=view).status_code == 200
        assert client.get('/overlay/alert', params=view).status_code == 200
        assert client.get('/api/state', headers={'X-View-Token':view['view_token']}).status_code == 200
        assert client.get('/api/graphics/top3', headers={'X-View-Token':view['view_token']}).status_code == 200
        assert client.get('/api/graphics/top3?preview=true', headers={'X-View-Token':view['view_token']}).status_code == 401
        assert client.get('/api/export/donations.csv', params=view).status_code == 401
        assert client.post('/api/simulate', params=view, json={'message':'#Marcus'}).status_code == 401
        result=client.post('/api/simulate', auth=('operator','a-very-long-operator-password'), json={'message':'#Marcus','amount':'25.00'})
        assert result.status_code==200
        state=client.get('/api/state',params=view).json()
        assert state['ranking'][0]['name']=='Marcus' and state['ranking'][0]['points']=='25.00'
        assert 'a-very-long-operator-password' not in client.get('/producers',params=view).text


def test_remote_mode_fails_closed_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DB_PATH', tmp_path/'blocked.sqlite3')
    monkeypatch.setattr(app_module, 'REMOTE_TEST', True)
    monkeypatch.setattr(app_module, 'OPERATOR_PASSWORD', '')
    monkeypatch.setattr(app_module, 'VIEW_TOKEN', '')
    try:
        with TestClient(app_module.app):
            raise AssertionError('Remote test must not start without secrets')
    except RuntimeError as exc:
        assert 'requires' in str(exc)


def test_haiti_theme_is_loaded_and_overlay_keeps_alpha():
    root=Path(__file__).resolve().parents[1]
    css=(root/'web/css/haiti-theme.css').read_text()
    assert all(c in css for c in ('#00209f','#d21034','#fff'))
    assert '.overlay-body,.overlay-html{background:transparent!important}' in css
    for page in ('operator.html','producer.html','overlay.html'):
        assert '/assets/css/haiti-theme.css' in (root/'web'/page).read_text()
    assert 'starter' in (root/'render.yaml').read_text()
