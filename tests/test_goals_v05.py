"""Goal workflows, donation-history corrections, and remote authorization boundaries."""
import pytest
from fastapi.testclient import TestClient
import app as app_module
import store
from pathlib import Path

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'goals.sqlite3')
    with TestClient(app_module.app) as c:
        yield c

def goal(client, **overrides):
    payload=dict(id='goal-4000',title='4,000 PWEN',metric='assigned_points',target='4000',
                 enabled=True,start_fresh=True,ticker='Ann rive 4,000 pwen!',sort_order=0)
    payload.update(overrides)
    resp=client.post('/api/goals',json=payload)
    assert resp.status_code==200,resp.text
    return resp.json()

def sim(client,**overrides):
    payload=dict(kind='superChatEvent',amount='25.00',currency='USD',message='#Marcus',donor='Alice')
    payload.update(overrides)
    response=client.post('/api/simulate',json=payload)
    assert response.status_code==200,response.text
    return response.json()

def test_goal_defaults_hidden_and_visibility(client,monkeypatch):
    monkeypatch.setattr(app_module,'PUBLIC_OVERLAYS',True)
    assert client.get('/api/goals').json()=={'visible':False,'goals':[]}
    assert client.get('/public/goals').json()['goals']==[] and client.get('/public/goals').json()['visible'] is False
    goal(client)
    assert client.get('/public/goals').json()['goals']==[]
    assert client.put('/api/goals/visibility',json={'visible':True}).status_code==200
    visible=client.get('/public/goals').json()['goals']
    assert len(visible)==1
    assert set(visible[0]) == {'id','title','metric','current','target','percent','complete','ends_at','ticker','enabled'}
    assert 'baseline' not in visible[0]
    assert client.put('/api/goals/visibility',json={'visible':False}).status_code==200
    assert client.get('/public/goals').json()['goals']==[]

def test_goal_auto_points_and_edited_assignment(client):
    sim(client,event_id='existing',message='#Marcus',amount='20')
    g=goal(client)
    assert g['current']=='0.00' # Start from time of goal creation.
    sim(client,event_id='after',message='#Avery',amount='10')
    assert client.get('/api/goals').json()['goals'][0]['current']=='10.00'
    # Correct assigned donation: assignment change doesn't create additional points.
    assert client.post('/api/assign',json={'donation_id':'after','cast_id':'marcus','reason':'Producer correction'}).status_code==200
    assert client.get('/api/goals').json()['goals'][0]['current']=='10.00'
    # Editing target retains goal baseline.
    patch=dict(id='goal-4000',title='Five Thousand',metric='assigned_points',target='5000',start_fresh=True)
    assert client.put('/api/goals/goal-4000',json=patch).status_code==200
    assert client.get('/api/goals').json()['goals'][0]['current']=='10.00'

def test_goal_combined_vs_real_only_and_duplicate(client):
    goal(client,id='allmoney',title='ALL USD',metric='donations_usd',target='100',start_fresh=False)
    goal(client,id='realmoney',title='REAL USD',metric='youtube_usd',target='100',start_fresh=False)
    sim(client,event_id='sim-first',amount='5',message='No tag')
    e={'id':'yt-superchat-1','snippet':{'type':'superChatEvent','superChatDetails':{
        'amountMicros':'20000000','currency':'USD','amountDisplayString':'$20', 'userComment':'#Marcus'}},
       'authorDetails':{'displayName':'YouTube Viewer'}}
    assert store.ingest(e,source='youtube')['result']=='created'
    assert store.ingest(e,source='youtube')['result']=='duplicate'
    data={g['id']:g for g in client.get('/api/goals').json()['goals']}
    assert data['allmoney']['current']=='25.00'
    assert data['realmoney']['current']=='20.00'
    assert data['allmoney']['percent']==25

def test_goal_cast_and_manual(client,monkeypatch):
    monkeypatch.setattr(app_module,'PUBLIC_OVERLAYS',True)
    g=goal(client,id='marcusgoal',title='Marcus Goal',metric='cast_points',cast_id='marcus',target='50',start_fresh=False)
    assert g['current']=='0.00'
    manual=goal(client,id='members',title='Gold members',metric='manual',target='100',manual_value='12',ticker='100 manm lò')
    assert manual['current']=='12.00'
    sim(client,amount='20',message='#Marcus')
    assert next(g for g in client.get('/api/goals').json()['goals'] if g['id']=='marcusgoal')['current']=='20.00'
    payload=dict(id='members',title='Gold members',metric='manual',target='100',manual_value='100',enabled=False)
    response=client.put('/api/goals/members',json=payload)
    assert response.status_code==200, response.text
    assert response.json()['complete'] and not response.json()['enabled']
    assert client.put('/api/goals/visibility',json={'visible':True}).status_code==200
    assert [g['id'] for g in client.get('/public/goals').json()['goals']]==['marcusgoal']

def test_goal_validation_and_delete(client):
    assert client.post('/api/goals',json={'id':'testgoal','title':'x','metric':'manual','target':'0'}).status_code==400
    assert client.post('/api/goals',json={'id':'testgoal','title':'x','metric':'cast_points','target':'100','cast_id':'ghost'}).status_code==400
    assert client.post('/api/goals',json={'id':'testgoal','title':'x','metric':'manual','target':'100','ends_at':'2027-01-01'}).status_code==400
    goal(client)
    assert client.post('/api/goals',json={'id':'goal-4000','title':'again','metric':'manual','target':'100'}).status_code==400
    assert client.put('/api/goals/different',json={'id':'goal-4000','title':'test','metric':'manual','target':'100'}).status_code==400
    assert client.delete('/api/goals/goal-4000').status_code==200
    assert client.get('/api/goals').json()['goals']==[]

def test_goal_reset_baseline_and_adjustment(client):
    sim(client,amount='30',message='#Marcus')
    goal(client,adjustment='5',target='100')
    assert client.get('/api/goals').json()['goals'][0]['current']=='5.00'
    sim(client,amount='10',message='#Marcus')
    patch=dict(id='goal-4000',title='Adjusted',metric='assigned_points',target='100', adjustment='-2', reset_baseline=True)
    assert client.put('/api/goals/goal-4000',json=patch).status_code==200
    assert client.get('/api/goals').json()['goals'][0]['current']=='0.00'
    sim(client,amount='15',message='#Marcus')
    assert client.get('/api/goals').json()['goals'][0]['current']=='13.00'

def test_history_search_and_assign_after_80_events(client):
    sim(client,event_id='old-donation',message='No hashtag',amount='50',donor='Historical Donor')
    for i in range(85):
        sim(client,event_id=f'new-{i}',message='No hashtag',amount='1')
    assert client.get('/api/state').json()['pending_count']==86
    assert 'old-donation' not in [x['id'] for x in client.get('/api/state').json()['pending']]
    hist=client.get('/api/donations',params={'q':'Historical Donor','status':'pending'}).json()
    assert hist['total']==1 and hist['items'][0]['id']=='old-donation'
    assert client.post('/api/assign',json={'donation_id':'old-donation','cast_id':'avery','reason':'Verified by producer'}).status_code==200
    assert client.get('/api/donations',params={'q':'old-donation','status':'pending'}).json()['total']==0
    assert client.get('/api/donations',params={'q':'old-donation','status':'assigned'}).json()['total']==1
    assert next(m for m in client.get('/api/state').json()['ranking'] if m['id']=='avery')['points']=='50.00'
    assert len(client.get('/api/donations',params={'limit':50,'offset':50,'status':'all'}).json()['items'])==36

def test_search_treats_special_like_characters_literally(client):
    sim(client,message='Test 100% stuff',event_id='percent-1')
    sim(client,message='Test 100_ stuff',event_id='under-1')
    assert client.get('/api/donations',params={'q':'%'}).json()['total']==1
    assert client.get('/api/donations',params={'q':'_'}).json()['total']==1

def test_goals_html_and_js_assets(client):
    assert client.get('/overlay/goals').status_code==200
    assert client.get('/overlay/top3-alert').status_code==200
    index=client.get('/').text
    assert 'id="tab-goals"' in index and 'id="donation-search-form"' in index
    root=Path(__file__).resolve().parents[1]
    js=(root/'js/overlay.js').read_text()
    assert "graphicId==='goals'" in js
    assert '/api/overlay/goals' in js
    setup=(root/'js/pages-setup.js').read_text()
    assert "'goals'" in setup

def test_goals_public_only_and_private_operator(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'private_goals.sqlite3')
    monkeypatch.setattr(app_module,'REMOTE_TEST',True)
    monkeypatch.setattr(app_module,'PUBLIC_OVERLAYS',True)
    monkeypatch.setattr(app_module,'OPERATOR_PASSWORD','long-example-operator-passphrase')
    monkeypatch.setattr(app_module,'VIEW_TOKEN','secret-view-token-that-is-long-enough')
    with TestClient(app_module.app) as c:
        assert c.get('/public/goals').status_code==200
        assert c.get('/api/goals').status_code==401
        assert c.get('/api/overlay/goals').status_code==401
        assert c.get('/api/donations').status_code==401
        assert c.post('/api/goals',json={'id':'g1','title':'bad','metric':'manual','target':'5'}).status_code==401
        assert c.put('/api/goals/visibility',json={'visible':True}).status_code==401
        assert c.get('/api/goals?view_token=secret-view-token-that-is-long-enough').status_code==401
        auth=('operator','long-example-operator-passphrase')
        assert c.post('/api/goals',json={'id':'g1','title':'Valid','metric':'manual','target':'5'},auth=auth).status_code==200
        assert c.put('/api/goals/visibility',json={'visible':True},auth=auth).status_code==200
        assert c.get('/public/goals').json()['goals'][0]['title']=='Valid'
        viewer = {'X-View-Token': 'secret-view-token-that-is-long-enough'}
        assert c.get('/api/overlay/goals', headers=viewer).json() == c.get('/public/goals').json()
        assert c.get('/api/donations',auth=auth).status_code==200
