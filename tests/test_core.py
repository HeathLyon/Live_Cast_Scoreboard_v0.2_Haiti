import pytest
from core import matched_cast_ids, validate_aliases, points_milli, classify_event, rank_members, parse_amount_to_micros

CAST = [{'id':'marcus','name':'Marcus','hashtags':['Marcus','TeamMarcus'],'active':True},
        {'id':'avery','name':'Avery','hashtags':['Avery'],'active':True},
        {'id':'taylor','name':'Taylor','hashtags':['Taylor'],'active':True}]

def event(i='evt1',kind='superChatEvent',amount=25000000,message='#Marcus',currency='USD'):
    return {'id':i,'snippet':{'type':kind,'superChatDetails':{'amountMicros':str(amount),'currency':currency,'userComment':message},'superStickerDetails':{'amountMicros':str(amount),'currency':currency}},'authorDetails':{'displayName':'Tester'}}

def test_single_hashtag_case_insensitive():
    assert matched_cast_ids('Go #mArCus and #TeamMarcus!', CAST)==['marcus']

def test_unknown_not_partial():
    assert matched_cast_ids('#Marcus123',CAST)==[]

def test_multiple_cast_review():
    assert classify_event(event(message='#Marcus #Avery'), CAST, '1')['status']=='review'

def test_no_tag_review():
    assert classify_event(event(message='hello'), CAST, '1')['status']=='review'

def test_free_chat_ignored():
    assert classify_event(event(kind='textMessageEvent'), CAST, '1') is None

def test_sticker_unassigned():
    assert classify_event(event(kind='superStickerEvent'), CAST, '1')['status']=='review'

def test_foreign_currency_not_usd():
    e=classify_event(event(currency='EUR'),CAST,'1')
    assert e['status']=='review_currency' and e['points_milli']==0

def test_money_decimal_and_multiplier():
    assert parse_amount_to_micros('12.50')==12500000
    assert points_milli(12500000,'10')==125000
    assert points_milli(1500000,'0.125')==188

def test_invalid_amount():
    with pytest.raises(ValueError):parse_amount_to_micros('NaN')
    with pytest.raises(ValueError):parse_amount_to_micros('1.001')

def test_hashtag_collision_rejected():
    with pytest.raises(ValueError):validate_aliases(CAST+[{'id':'new','name':'New','hashtags':['#MARCUS'],'active':True}])

def test_rank_order_and_tie_policy():
    r=rank_members(CAST, {'marcus':100,'avery':100,'taylor':200})
    assert [x['id'] for x in r]==['taylor','avery','marcus']
