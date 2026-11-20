import pytest
from fastapi.testclient import TestClient
import store
from app import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'unit.sqlite3')
    with TestClient(app) as c:
        yield c

def sim(c, amount='20.00',message='#Marcus',kind='superChatEvent',event_id=None,currency='USD'):
    payload={'amount':amount,'message':message,'kind':kind,'currency':currency}
    if event_id:payload['event_id']=event_id
    r=c.post('/api/simulate',json=payload);assert r.status_code==200,r.text
    return r.json()

def test_pages_serve(client):
    for url in ['/', '/producers','/overlay/top3','/overlay/alert','/overlay/full','/health']:
        assert client.get(url).status_code==200
    assert 'id="tab-system"' in client.get('/').text
    assert client.get('/overlay/unknown').status_code==404

def test_superchat_updates_top3_and_alert(client):
    r=sim(client,amount='20.00',message='Go #Marcus',event_id='test1')
    assert r['result']=='created' and r['status']=='assigned'
    s=client.get('/api/state').json();assert s['ranking'][0]['name']=='Marcus'
    assert s['ranking'][0]['points']=='20.00'
    a=client.get('/api/alerts?after=0').json()['alerts']
    assert len(a)==1 and a[0]['new_total']=='20.00' and a[0]['rank']==1

def test_duplicate_no_double_credit_or_second_alert(client):
    assert sim(client,event_id='same')['result']=='created'
    assert sim(client,event_id='same')['result']=='duplicate'
    assert client.get('/api/state').json()['event_count']==1
    assert len(client.get('/api/alerts?after=0').json()['alerts'])==1

def test_review_and_manual_assign_with_rank(client):
    sim(client,amount='25.00',message='#Marcus #Avery',event_id='ambiguous')
    s=client.get('/api/state').json();assert s['pending_count']==1
    assert all(x['points']=='0.00' for x in s['ranking'])
    r=client.post('/api/assign',json={'donation_id':'ambiguous','cast_id':'jordan','reason':'Producer chose Jordan'})
    assert r.status_code==200
    s=client.get('/api/state').json();assert s['ranking'][0]['id']=='jordan'
    assert len(client.get('/api/alerts?after=0').json()['alerts'])==1

def test_free_chat_and_sticker(client):
    assert sim(client,kind='textMessageEvent')['result']=='ignored'
    assert sim(client,kind='superStickerEvent',event_id='sticker')['status']=='review'
    s=client.get('/api/state').json()
    assert s['event_count']==1 and s['pending_count']==1
    assert s['gross_usd']=='20.00'

def test_foreign_currency_review(client):
    r=sim(client,currency='EUR',event_id='foreign')
    assert r['status']=='review_currency'
    assert client.get('/api/state').json()['gross_usd']=='0.00'
    assert client.post('/api/assign',json={'donation_id':'foreign','cast_id':'marcus','reason':'test'}).status_code==400

def test_future_only_multiplier(client):
    sim(client,amount='5',message='#Marcus',event_id='early')
    assert client.put('/api/settings',json={'points_per_usd':'10'}).status_code==200
    sim(client,amount='5',message='#Marcus',event_id='late')
    s=client.get('/api/state').json()
    assert next(x for x in s['ranking'] if x['id']=='marcus')['points']=='55.00'
    assert len(client.get('/api/alerts?after=0').json()['alerts'])==2

def test_graphics_draft_preview_and_publish(client):
    assert client.get('/api/graphics/top3').json()['title_ht']=='3 PREMYE YO'
    payload={'name':'Live Night Graphic','accent':'#aabbcc','position':'right','scale':'large',
             'title_en':'NIGHT','title_ht':'NOUVO KLASEMAN','duration':5,'enabled':True}
    assert client.put('/api/graphics/top3/draft',json=payload).status_code==200
    assert client.get('/api/graphics/top3?preview=true').json()['title_ht']=='NOUVO KLASEMAN'
    assert client.get('/api/graphics/top3').json()['title_ht']=='3 PREMYE YO'
    assert client.post('/api/graphics/top3/publish').status_code==200
    assert client.get('/api/graphics/top3').json()['title_ht']=='NOUVO KLASEMAN'

def test_clone_and_rename_graphic(client):
    response=client.post('/api/graphics',json={'source_id':'top3','id':'night-shift','name':'Night Shift'})
    assert response.status_code==200
    assert client.get('/overlay/night-shift').status_code==200

def test_cast_edit_collision(client):
    assert client.post('/api/cast',json={'id':'newperson','name':'New Person','hashtags':['NewPerson'],'active':True}).status_code==200
    assert client.post('/api/cast',json={'id':'another','name':'Another','hashtags':['Marcus'],'active':True}).status_code==400

def test_csv_export_and_reset(client):
    sim(client,event_id='e-123')
    data=client.get('/api/export/donations.csv')
    assert data.status_code==200 and 'e-123' in data.text
    assert client.post('/api/reset',json={'confirm':'wrong'}).status_code==400
    assert client.post('/api/reset',json={'confirm':'RESET DEMO'}).status_code==200
    assert client.get('/api/state').json()['event_count']==0

def test_rank_of_outside_top3(client):
    sim(client,amount='100',message='#Marcus')
    sim(client,amount='80',message='#Avery')
    sim(client,amount='60',message='#Jordan')
    sim(client,amount='5',message='#Taylor',event_id='tail')
    a=client.get('/api/alerts?after=0').json()['alerts'][-1]
    assert a['cast_name']=='Taylor' and a['rank']==4 and a['new_total']=='5.00'

def test_persistence_survives_restart(client):
    sim(client,amount='30',message='#Avery',event_id='restart-proof')
    store.initialize() # Non-destructive startup simulating service reboot.
    assert client.get('/api/state').json()['event_count']==1
    assert sim(client,event_id='restart-proof')['result']=='duplicate'
