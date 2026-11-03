import copy
import pytest
from backend.catalog import HAZARDS,REGIONS
from backend.scenarios import create_world,add_incident
from backend.planner import build_plan
from backend.engine import advance,commit,metrics,transfer
from backend.routing import network,route
from backend.coordination import placement

def local(hazard='road',patients=2,evacuees=0):
    s=create_world('heatwave',seed=7,region='RJ',hazard=hazard,count=1)
    s['resources']=[r for r in s['resources'] if r['region']=='RJ']
    s['facilities']=[f for f in s['facilities'] if f['region']=='RJ']
    s['incidents']=[];s['patients']=[]
    add_incident(s,'RJ',hazard,'critical',patients,evacuees)
    return s

def assert_capacity(s):
    for f in s['facilities']:
        if f['kind']=='shelter':
            assert 0<=f['shelter_occupied']+f['shelter_reserved']<=f['capacity'];continue
        cuts=sorted(set([0,f['baseline_release']]+[t for r in f['reservations'] for t in [r['start'],r['end']]]))
        for a,b in zip(cuts,cuts[1:]):
            t=(a+b)/2
            used=sum(r['start']<=t<r['end'] for r in f['reservations'])+(f['baseline_occupied'] if t<f['baseline_release'] else 0)
            assert used<=f['capacity'],(f['id'],t,used,f['capacity'])
    for r in s['resources']:
        assignments=sorted([m for m in s['missions'] if m['resource_id']==r['id']],key=lambda m:m['started_at'])
        for a,b in zip(assignments,assignments[1:]):assert a['available_at']<=b['started_at']+1e-6

@pytest.mark.parametrize('hazard',list(HAZARDS))
def test_each_disaster_completes_prerequisites_transport_and_care(hazard):
    s=local(hazard,2,8 if hazard in ('flood','cyclone','tsunami') else 0)
    advance(s,240)
    assert all(p['status']=='completed' for p in s['patients'])
    assert s['incidents'][0]['rescue_status']=='completed'
    assert s['incidents'][0]['evacuated']==s['incidents'][0]['evacuees']
    for p in s['patients']:
        m=next(m for m in s['missions'] if m.get('patient_id')==p['id'])
        assert m['depart_at']>=s['incidents'][0]['rescue_ready']
        assert m['treatment_at']>=m['arrival_at']>=m['depart_at']>=m['response_at']
        resource=next(r for r in s['resources'] if r['id']==m['resource_id'])
        if p['severity']=='critical':assert resource['type']=='als'
        f=next(f for f in s['facilities'] if f['id']==m['facility_id'])
        assert p['care'] in f['capabilities']
    assert_capacity(s)

def test_capacity_and_resource_exclusivity_under_scarcity():
    s=local('fire',6)
    for f in s['facilities']:
        if f['kind']=='hospital':f.update(capacity=1,baseline_occupied=0)
    add_incident(s,'RJ','fire','critical',5)
    advance(s,360)
    assert_capacity(s)
    assert metrics(s)['treated']>0

def test_stale_and_duplicate_dispatch_rejected():
    s=local();p=build_plan(s);commit(s,p)
    with pytest.raises(ValueError,match='scenario changed'):commit(s,p)
    p=build_plan(local());p['assignments'].append(copy.deepcopy(p['assignments'][0]))
    with pytest.raises(ValueError,match='resource'):commit(local(),p)

def test_blocked_graph_returns_no_path_and_no_fake_direct_route():
    s=local();g=network('RJ');nodes=list(g.nodes)
    blocked={'closed_edges':{'RJ':[f'{a}:{b}' for a,b in g.edges]},'traffic':1}
    assert route('RJ',nodes[0],nodes[-1],blocked) is None
    assert route('RJ',nodes[0],nodes[-1],{'traffic':1}) is not None

def test_severe_weather_holds_air_and_water_rescue():
    s=local('flood',2,6);s['conditions']['weather']='severe'
    p=build_plan(s)
    assert not p['rescues'] and not p['assignments']
    advance(s,20);assert metrics(s)['unserved']==2
    s['conditions']['weather']='normal';advance(s,220)
    assert metrics(s)['treated']==2

def test_unavailable_advanced_ambulances_never_replaced_with_basic():
    s=local()
    for r in s['resources']:
        if r['type']=='als':r['status']='offline'
    p=build_plan(s)
    assert s['patients'][0]['id'] not in {a['patient_id'] for a in p['assignments']}
    assert any(u['patient_id']==s['patients'][0]['id'] for u in p['unassigned'])

def test_unknown_future_incidents_do_not_enter_plan():
    s=local();i=add_incident(s,'RJ','road','critical',2,reported_at=120)
    p=build_plan(s)
    assert i['id'] not in {a['incident_id'] for a in p['rescues']+p['assignments']}
    assert metrics(s)['incidents']==1

def test_same_seed_and_policy_produce_same_small_run():
    a=local('rail');b=local('rail');advance(a,180);advance(b,180)
    assert metrics(a)==metrics(b)
    assert a['events']==b['events']

def test_mutual_aid_preserves_reserves_and_requires_travel():
    s=create_world('heatwave');r=next(r for r in s['resources'] if r['region']=='MP' and r['type']=='als')
    with pytest.raises(ValueError,match='reserve'):transfer(s,r['id'],'RJ',reserve=2)
    tr=transfer(s,r['id'],'RJ',reserve=1)
    assert r['status']=='transferring' and r['region']=='MP'
    assert tr['arrival_at']>s['now']
    advance(s,tr['arrival_at']+1,auto=False)
    assert r['region']=='RJ' and r['status']=='available'

def test_prepositioning_respects_donor_minima():
    s=create_world('heatwave');p=placement(s,'RJ','als',5,1)
    assert len(p['assignments'])==3 and p['unmet']==0
    assert len({a['from_region'] for a in p['assignments']})==3
    assert all(a['minutes']>0 for a in p['assignments'])

def test_no_treated_patients_reports_null_times_and_unmet_demand():
    s=local();m=metrics(s)
    assert m['time_to_care']['mean'] is None
    assert m['unserved']==m['patients']==2

def test_closed_facility_not_selected_and_shelter_capacity_conserved():
    s=local('cyclone',3,25)
    for f in s['facilities']:
        if f['id']=='RJ-H1':f['closed']=True
        if f['kind']=='shelter':f['capacity']=9
    p=build_plan(s);assert all(a['facility_id']!='RJ-H1' for a in p['assignments'])
    advance(s,240);assert s['incidents'][0]['evacuated']==9
    assert_capacity(s)

def test_all_states_and_union_territories_have_resource_packages():
    assert len(REGIONS)==36
    s=create_world()
    for region in REGIONS:
        assert any(r['region']==region['id'] for r in s['resources'])
        assert any(f['region']==region['id'] for f in s['facilities'])

def test_capacity_aware_destination_avoids_saturated_nearest_hospital():
    a=create_world('capacity',seed=7,region='RJ',count=1)
    b=copy.deepcopy(a)
    advance(a,180,'nearest');advance(b,180,'optimized')
    ma,mb=metrics(a),metrics(b)
    assert ma['unserved']==mb['unserved']==0
    assert mb['time_to_care']['mean']<ma['time_to_care']['mean']
    assert ma['hospital_wait']['mean']>mb['hospital_wait']['mean']

def test_helicopter_performs_configured_hoist_rescue_when_ground_team_unavailable():
    s=local('landslide')
    for r in s['resources']:
        if r['type']=='mountain_rescue':r['status']='offline'
    plan=build_plan(s)
    assert len(plan['rescues'])==1
    assert plan['rescues'][0]['route']['mode']=='air'
    commit(s,plan);advance(s,180)
    assert metrics(s)['unserved']==0
