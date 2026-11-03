from __future__ import annotations
import copy
import random
from .catalog import REGIONS, REGION_BY_ID, HAZARDS, PRESETS, RESOURCE_TYPES
from .routing import network, node_position

def stable_seed(seed, text):
    import hashlib
    return int(hashlib.sha256(f'{seed}:{text}'.encode()).hexdigest()[:12],16)

def add_incident(state, region, hazard, severity, patients, evacuees=0, title=None, node=None, reported_at=None):
    index=len(state['incidents'])+1
    iid=f'INC-{index:04d}'
    rng=random.Random(stable_seed(state['seed'],iid))
    nodes=list(network(region).nodes)
    node=str(node) if node is not None else nodes[rng.randrange(len(nodes))]
    if node not in network(region):
        raise ValueError('Location is outside the loaded transport network')
    t=state['now'] if reported_at is None else reported_at
    h=HAZARDS[hazard]
    inc=dict(id=iid,region=region,hazard=hazard,severity=severity,title=title or f"{h['name']} · {REGION_BY_ID[region]['city']}",
             node=node,position=node_position(region,node),reported_at=t,occurred_at=t-rng.randint(2,7),
             rescue_status='waiting',rescue_ready=None,rescue_assignment=None,patients=[],evacuees=evacuees,
             evacuated=0,evac_reserved=0,first_response=None,source='Simulated incident',steps=h['steps'],
             rescue_duration=round(h['duration']*rng.uniform(.85,1.2),1),supplies_delivered=0)
    for j in range(patients):
        sev=severity if j==0 else ('serious' if severity=='critical' and j%2 else 'minor')
        pid=f'{iid}-P{j+1:02d}'
        p=dict(id=pid,incident_id=iid,severity=sev,status='waiting',assignment=None,care=h['care'],
               response_at=None,treatment_at=None,completed_at=None,
               treatment_duration=rng.randint(28,44) if sev=='critical' else rng.randint(14,28),
               scene_duration=rng.randint(3,6),wait_reason='Awaiting allocation')
        state['patients'].append(p)
        inc['patients'].append(pid)
    state['incidents'].append(inc)
    return inc

def create_world(preset='national',seed=42,region=None,hazard=None,count=None,extra_ambulances=0):
    p=next((p for p in PRESETS if p['id']==preset),PRESETS[0])
    chosen_region=region or p['region']
    chosen_hazard=hazard or p['hazard']
    state=dict(schema_version=1,id='',revision=0,now=0.0,seed=seed,preset=preset,region=chosen_region,
               conditions=dict(traffic=1.35,weather='normal',closed_edges={}),
               incidents=[],patients=[],resources=[],facilities=[],missions=[],events=[],transfers=[],disruptions=[],
               settings=dict(policy='optimized',auto_dispatch=True),last_plan=None,
               description=p['description'],next_event_id=1)
    types=['als','als','bls','bls','bls','bls','rescue','heavy_rescue','boat','mountain_rescue','fire_engine','hazmat','medical_team','supply_truck','bus','bus','helicopter']
    for r in REGIONS:
        nodes=list(network(r['id']).nodes)
        rng=random.Random(stable_seed(seed,r['id']))
        for j,kind in enumerate(types+['als']*extra_ambulances):
            n=nodes[rng.randrange(len(nodes))]
            state['resources'].append(dict(id=f"{r['id']}-{kind.upper()}-{j+1:02d}",name=RESOURCE_TYPES[kind],type=kind,
                region=r['id'],home_region=r['id'],node=n,position=node_position(r['id'],n),status='available',
                assignment=None,available_at=0.0,capacity=20 if kind=='bus' else (6 if kind=='boat' else (2 if kind=='helicopter' else 1)),busy_minutes=0.0))
        for j,(name,caps,bays) in enumerate([
            ('Regional Medical Centre',['general','trauma'],3),
            ('District Emergency Hospital',['general','trauma','burns','isolation'],4),
            ('Specialist Care Centre',['general','burns','isolation'],2),
            ('Community Shelter',[],80),
        ]):
            n=nodes[min(len(nodes)-1,int(len(nodes)*[.24,.73,.51,.43][j]))]
            state['facilities'].append(dict(id=f"{r['id']}-H{j+1}",name=f"{r['city']} {name}",region=r['id'],node=n,
                position=node_position(r['id'],n),kind='shelter' if not caps else 'hospital',capabilities=caps,
                capacity=bays,baseline_occupied=0 if not caps else (1 if j<2 else 0),baseline_release=35.0,
                closed=False,reservations=[],shelter_reserved=0,shelter_occupied=0,source='Synthetic demonstration facility'))
    if chosen_region=='ALL':
        places=['AS','TN','OD','DL','MH','UK','GJ','KL','AN','RJ','BR','WB']
        hazards=['flood','road','cyclone','road','fire','landslide','earthquake','flood','tsunami','heatwave','epidemic','rail']
        for j in range(count or p['count']):
            hz=hazards[j%len(hazards)] if chosen_hazard=='mixed' else chosen_hazard
            add_incident(state,places[j%len(places)],hz,'critical' if j%3==0 else 'serious',2+j%3,
                         evacuees=12+j*2 if hz in ['flood','cyclone','tsunami'] else 0)
    else:
        for j in range(count or p['count']):
            hz=list(HAZARDS)[j%len(HAZARDS)] if chosen_hazard=='mixed' else chosen_hazard
            add_incident(state,chosen_region,hz,'critical' if j%3==0 else 'serious',2+j%3,
                         evacuees=10+j*3 if hz in ['flood','cyclone','tsunami'] else 0,
                         reported_at=0 if j<3 else (j-2)*12)
    if preset=='compound':
        state['disruptions']=[dict(at=18,kind='hospital',target='KL-H1',applied=False),dict(at=32,kind='corridor',target='KL',applied=False)]
    if preset=='capacity' and chosen_region!='ALL':
        near=next(f for f in state['facilities'] if f['id']==f'{chosen_region}-H1')
        near.update(capacity=2,baseline_occupied=2,baseline_release=120)
        other=next(f for f in state['facilities'] if f['id']==f'{chosen_region}-H2')
        other.update(baseline_occupied=0)
        for inc in state['incidents']:
            inc.update(node=near['node'],position=near['position'])
    state['initial_config']=dict(preset=preset,seed=seed,region=chosen_region,hazard=chosen_hazard,count=count or p['count'],extra_ambulances=extra_ambulances)
    state['data_versions']={r['id']:network(r['id']).graph['fingerprint'] for r in REGIONS}
    state['decisions']=[]
    return state

def clone(state):
    return copy.deepcopy(state)
