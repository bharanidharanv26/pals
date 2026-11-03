import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.alerts import parse_cap

client=TestClient(app)

@pytest.fixture
def workspace():
    r=client.post('/api/sessions',json={'preset':'chennai_city','region':'CHN-C','count':1})
    assert r.status_code==200
    return {'X-Session-ID':r.json()['id']}

def test_isolated_workspaces_and_private_plans(workspace):
    second=client.post('/api/sessions',json={'preset':'chennai_city','count':1}).json()
    p=client.post('/api/plans',json={},headers=workspace).json()
    forbidden=client.post('/api/plans/commit',json={'plan_id':p['id']},headers={'X-Session-ID':second['id']})
    assert forbidden.status_code==409
    before=client.get('/api/state',headers={'X-Session-ID':second['id']}).json()['revision']
    assert client.post('/api/plans/commit',json={'plan_id':p['id']},headers=workspace).status_code==200
    assert client.get('/api/state',headers={'X-Session-ID':second['id']}).json()['revision']==before

def test_input_validation_and_missing_session(workspace):
    assert client.get('/api/state').status_code==401
    assert client.post('/api/incidents',json={'region':'XX','hazard':'road','patients':1},headers=workspace).status_code==422
    assert client.post('/api/advance',json={'minutes':999999},headers=workspace).status_code==422
    assert client.post('/api/incidents',json={'region':'CHN-C','hazard':'road','patients':0},headers=workspace).status_code==422
    assert client.post('/api/incidents',json={'region':'CHN-C','hazard':'road','latitude':13,'longitude':80},headers=workspace).status_code==409
    assert client.post('/api/incidents',json={'region':'CHN-C','hazard':'road','latitude':28.6,'longitude':77.2},headers=workspace).status_code==422

def test_revision_rejects_stale_recommendation_after_disruption(workspace):
    p=client.post('/api/plans',json={},headers=workspace).json()
    assert client.patch('/api/conditions',json={'traffic':2},headers=workspace).status_code==200
    assert client.post('/api/plans/commit',json={'plan_id':p['id']},headers=workspace).status_code==409

def test_exports_contain_scenario_and_event_records(workspace):
    client.post('/api/advance',json={'minutes':5},headers=workspace)
    response=client.get('/api/export?kind=snapshot',headers=workspace)
    assert response.status_code==200 and response.json()['initial_config']['seed']==42
    response=client.get('/api/export?kind=events',headers=workspace)
    assert 'text/csv' in response.headers['content-type']
    assert 'id,at,kind,message,incident_id' in response.text

def test_cap_import_preserves_status_and_does_not_create_incidents(workspace):
    xml='''<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>test-1</identifier><sender>example</sender><status>Exercise</status><info><event>Flood</event><severity>Severe</severity><headline>Exercise warning</headline><area><areaDesc>Demo area</areaDesc><polygon>26,91 26.1,91 26,91.1 26,91</polygon></area></info></alert>'''
    original=client.get('/api/state',headers=workspace).json()['metrics']['incidents']
    response=client.post('/api/alerts/import',json={'xml':xml},headers=workspace)
    assert response.status_code==200
    assert response.json()['items'][0]['status']=='Exercise'
    assert response.json()['items'][0]['polygon'][0]==[91,26]
    assert client.get('/api/state',headers=workspace).json()['metrics']['incidents']==original

def test_xml_external_entity_is_rejected(workspace):
    xml='<!DOCTYPE alert [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><alert><info><headline>&xxe;</headline></info></alert>'
    assert client.post('/api/alerts/import',json={'xml':xml},headers=workspace).status_code==422

def test_data_and_network_endpoints_have_traceable_sources():
    catalog=client.get('/api/catalog').json()
    assert len(catalog['regions'])==8 and len(catalog['hazards'])==12
    assert all(r['id'].startswith('CHN-') for r in catalog['regions'])
    assert len(catalog['sources'])==2
    roads=client.get('/api/networks/CHN-C').json()
    assert roads['features'][0]['properties']['source']=='osm'
    assert client.get('/api/networks/NOT-A-REGION').status_code==404

def test_default_session_creates_a_chennai_scenario():
    response=client.post('/api/sessions',json={})
    assert response.status_code==200
    body=response.json()
    assert body['region']=='CHN-C' and body['incidents']
    assert body['initial_config']['preset']=='chennai_city'

def test_hospital_saturation_preset_is_applied():
    body=client.post('/api/sessions',json={'preset':'chennai_capacity'}).json()
    h1=next(f for f in body['facilities'] if f['id']=='CHN-S-H1')
    assert h1['capacity']==2 and h1['occupied']==2
    assert all(i['node']==h1['node'] for i in body['incidents'])
