from __future__ import annotations
import copy
import math
import statistics
import simpy
from .catalog import HAZARDS, REGION_BY_ID
from .planner import build_plan, next_slot
from .routing import route, node_position, nearest, distance, network

def emit(state,kind,message,incident_id=None,at=None):
    state['events'].append(dict(id=state['next_event_id'],at=state['now'] if at is None else at,kind=kind,message=message,incident_id=incident_id))
    state['next_event_id']+=1

def commit(state,plan):
    if plan['revision']!=state['revision'] or plan['at']!=state['now']:
        raise ValueError('The scenario changed. Calculate a new plan before dispatching.')
    resources={r['id']:r for r in state['resources']}
    patients={p['id']:p for p in state['patients']}
    incidents={i['id']:i for i in state['incidents']}
    facilities={f['id']:f for f in state['facilities']}
    all_rows=plan['rescues']+plan['assignments']+plan['evacuations']
    ids=[c['resource_id'] for c in all_rows]
    if len(ids)!=len(set(ids)) or any(resources[r]['status']!='available' for r in ids):
        raise ValueError('A resource is no longer available. Recalculate the plan.')
    for row in all_rows:
        m=copy.deepcopy(row)
        m.update(id=f"M{len(state['missions'])+1:05d}",started_at=state['now'],phase='outbound',flags=[],completed=False)
        state['missions'].append(m)
        r=resources[m['resource_id']]
        r.update(status='dispatched',assignment=m['id'],available_at=m['available_at'])
        inc=incidents[m['incident_id']]
        if m['type']=='rescue':
            inc.update(rescue_status='active',rescue_ready=m['ready_at'],evac_ready_at=m.get('evac_ready_at',m['ready_at']),rescue_assignment=m['id'],pickup_node=m['pickup_node'],steps=m['steps'])
        elif m['type']=='patient':
            patients[m['patient_id']].update(status='dispatched',assignment=m['id'],wait_reason=None)
            f=facilities[m['facility_id']]
            f['reservations'].append(dict(mission=m['id'],start=m['treatment_at'],end=m['treatment_at']+m['duration']))
        else:
            inc['evac_reserved']+=m['people'];facilities[m['facility_id']]['shelter_reserved']+=m['people']
        emit(state,'dispatch',f"{r['id']} assigned to {inc['id']}",inc['id'])
    for u in plan['unassigned']:
        patients[u['patient_id']]['wait_reason']=u['reason']
    state['last_plan']=plan
    state.setdefault('decisions',[]).append(dict(at=plan['at'],policy=plan['policy'],solver_status=plan['solver_status'],runtime_ms=plan['runtime_ms'],candidate_count=plan['candidate_count'],
        assignments=[dict(type=row['type'],resource_id=row['resource_id'],incident_id=row['incident_id'],patient_id=row.get('patient_id'),facility_id=row.get('facility_id')) for row in all_rows]))
    state['revision']+=1
    return len(all_rows)

def position_on(path,progress):
    points=path['coordinates']
    if len(points)<2:return points[0]
    lengths=[distance(a,b) for a,b in zip(points,points[1:])]
    target=sum(lengths)*min(1,max(0,progress))
    for a,b,d in zip(points,points[1:],lengths):
        if target<=d:
            f=target/d if d else 1
            return [a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f]
        target-=d
    return points[-1]

def remove_reservation(f,mission_id):
    f['reservations']=[r for r in f['reservations'] if r['mission']!=mission_id]

def prepare_transport(state,m,now,from_node=None):
    """Re-route at leg boundaries. Existing in-flight legs remain committed."""
    f_by={f['id']:f for f in state['facilities']}
    old=f_by[m['facility_id']]
    region=old['region'];pickup=from_node or m.get('held_node') or m['pickup_node']
    if m['type']=='patient':
        p=next(p for p in state['patients'] if p['id']==m['patient_id'])
        options=[f for f in state['facilities'] if f['kind']=='hospital' and f['region']==region and not f['closed'] and p['care'] in f['capabilities']]
    else:
        options=[f for f in state['facilities'] if f['kind']=='shelter' and f['region']==region and not f['closed'] and (f['id']==old['id'] or f['capacity']-f['shelter_occupied']-f['shelter_reserved']>=m['people'])]
    choices=[]
    if m['type']=='patient':remove_reservation(old,m['id'])
    for f in options:
        path=route(region,pickup,f['node'],state['conditions'])
        if path:
            arrival=now+path['minutes']
            care=next_slot(f,arrival,m['duration']) if m['type']=='patient' else arrival
            # Preserve selected hospital when it is still reachable and open.
            choices.append((0 if f['id']==old['id'] else 1,care,f,path,arrival))
    if not choices:
        m['phase']='waiting_route'
        m['held_node']=pickup
        if m['type']=='patient':p['status']='waiting_route';p['wait_reason']='Transport held: no reachable suitable facility'
        return False
    _,care,f,path,arrival=min(choices,key=lambda c:(c[0],c[1],c[2]['id']))
    if m['type']=='evacuation' and f['id']!=old['id']:
        old['shelter_reserved']-=m['people'];f['shelter_reserved']+=m['people']
    m.update(facility_id=f['id'],transport_route=path,depart_at=now,arrival_at=arrival,phase='transport')
    m.pop('held_node',None)
    if m['type']=='patient':
        m['treatment_at']=care;m['available_at']=care+9
        f['reservations'].append(dict(mission=m['id'],start=care,end=care+m['duration']))
        p['status']='transport'
    else:m['available_at']=arrival+8
    next(r for r in state['resources'] if r['id']==m['resource_id'])['available_at']=m['available_at']
    return True

def process(state,now,dt):
    resources={r['id']:r for r in state['resources']}
    incs={i['id']:i for i in state['incidents']}
    patients={p['id']:p for p in state['patients']}
    facilities={f['id']:f for f in state['facilities']}
    for r in resources.values():
        if r['status'] not in ('available','offline'):r['busy_minutes']+=dt
    for tr in state['transfers']:
        if tr['status']=='arrived':continue
        r=resources[tr['resource_id']]
        frac=min(1,(now-tr['started_at'])/(tr['arrival_at']-tr['started_at']))
        r['position']=[a+(b-a)*frac for a,b in zip(tr['origin'],tr['destination'])]
        if now>=tr['arrival_at']:
            target=tr['to_region'];n=nearest(target,tr['destination'])
            r.update(region=target,node=n,position=node_position(target,n),status='available',assignment=None)
            tr['status']='arrived';emit(state,'transfer',f"{r['id']} arrived in {REGION_BY_ID[target]['name']}")
    for m in state['missions']:
        if m['completed']:continue
        r=resources[m['resource_id']];inc=incs[m['incident_id']]
        owns=r['assignment']==m['id']
        path=m.get('route') or m['response_route']
        if now<m['response_at']:
            if owns:r['position']=position_on(path,(now-m['started_at'])/max(.1,m['response_at']-m['started_at']))
            continue
        if 'response' not in m['flags']:
            m['flags'].append('response')
            inc['first_response']=min(inc['first_response'] or m['response_at'],m['response_at'])
            if owns:r.update(position=path['coordinates'][-1],node=path['nodes'][-1],status='on_scene')
            if m['type']=='patient':patients[m['patient_id']]['response_at']=m['response_at']
            emit(state,'arrival',f"{r['id']} reached the response location",inc['id'],m['response_at'])
        if m['type']=='rescue':
            m['phase']='rescuing'
            return_leg=m.get('transfer_route')
            if owns and return_leg and m['ready_at']-return_leg['minutes']<=now<m['ready_at']:
                r['position']=position_on(return_leg,1-(m['ready_at']-now)/max(.1,return_leg['minutes']))
            if now>=m['ready_at'] and 'rescued' not in m['flags']:
                m['flags'].append('rescued');inc['rescue_status']='completed'
                if inc['hazard']=='drought':inc['supplies_delivered']=1
                if owns:r.update(node=m['pickup_node'],position=node_position(r['region'],m['pickup_node']))
                emit(state,'rescue',f"{inc['id']}: rescue prerequisites completed",inc['id'],m['ready_at'])
            if now>=m['available_at']:
                if owns:r.update(status='available',assignment=None)
                m.update(completed=True,phase='completed')
            continue
        if m['phase'] in ('outbound','waiting_route') and now>=m['depart_at']:
            if not prepare_transport(state,m,max(m['depart_at'],now if m['phase']=='waiting_route' else m['depart_at'])):continue
            emit(state,'transport',f"{r['id']} transporting to {m['facility_id']}",inc['id'],m['depart_at'])
        if m['phase'] in ('outbound','waiting_route'):
            if m['type']=='patient':patients[m['patient_id']]['status']='on_scene'
            continue
        f=facilities[m['facility_id']]
        if now<m['arrival_at']:
            if owns:r.update(status='transport',position=position_on(m['transport_route'],(now-m['depart_at'])/max(.1,m['arrival_at']-m['depart_at'])))
            continue
        if 'facility' not in m['flags']:
            if f['closed']:
                if owns:r.update(node=f['node'],position=f['position'])
                if not prepare_transport(state,m,now,from_node=f['node']):continue
                continue
            m['flags'].append('facility')
            if owns:r.update(node=f['node'],position=f['position'],status='handover')
            emit(state,'hospital' if m['type']=='patient' else 'shelter',f"{r['id']} arrived at {f['name']}",inc['id'],m['arrival_at'])
            if m['type']=='evacuation':
                inc['evac_reserved']-=m['people'];inc['evacuated']+=m['people']
                f['shelter_reserved']-=m['people'];f['shelter_occupied']+=m['people']
        if m['type']=='patient':
            p=patients[m['patient_id']]
            if now<m['treatment_at']:
                p['status']='hospital_queue';m['phase']='hospital_queue'
            elif 'treatment' not in m['flags']:
                p.update(status='treatment',treatment_at=m['treatment_at']);m['phase']='treatment';m['flags'].append('treatment')
                emit(state,'treatment',f"{p['id']} started appropriate {p['care']} care",inc['id'],m['treatment_at'])
            if now>=m['treatment_at']+m['duration']:
                p.update(status='completed',completed_at=m['treatment_at']+m['duration']);m.update(completed=True,phase='completed')
        elif now>=m['available_at']:m.update(completed=True,phase='completed')
        if now>=m['available_at'] and owns:
            r.update(status='available',assignment=None)
    for d in state['disruptions']:
        if d['applied'] or now<d['at']:continue
        d['applied']=True
        if d['kind']=='hospital':
            facilities[d['target']]['closed']=True
            emit(state,'disruption',f"Scheduled facility outage: {d['target']}")
        else:
            close_corridor(state,d['target'])

def advance(state,minutes,policy=None,auto=True):
    policy=policy or state['settings']['policy']
    env=simpy.Environment(initial_time=state['now'])
    started=state['now']
    until=state['now']+minutes
    def run():
        while env.now<until:
            if auto and (int(env.now)%3==0 or env.now==started):
                plan=build_plan(state,policy)
                if plan['rescues'] or plan['assignments'] or plan['evacuations']:commit(state,plan)
            dt=min(1,until-env.now)
            yield env.timeout(dt)
            state['now']=float(env.now)
            process(state,state['now'],dt)
    env.process(run());env.run()
    state['revision']+=1
    return state

def close_corridor(state,region):
    g=network(region)
    # Remove several directed edges around a hub, leaving alternate routes where possible.
    hub=list(g.nodes)[len(g)//2]
    edges=[f'{a}:{b}' for a,b in list(g.in_edges(hub))+list(g.out_edges(hub))]
    closed=state['conditions']['closed_edges'].setdefault(region,[])
    closed.extend(e for e in edges[:max(2,len(edges)//2)] if e not in closed)
    emit(state,'disruption',f"Road corridor closed in {REGION_BY_ID[region]['name']}")
    return edges

def transfer(state,resource_id,to_region,reserve=1):
    r=next((r for r in state['resources'] if r['id']==resource_id),None)
    if not r or r['status']!='available':raise ValueError('Select an available resource')
    if r['region']==to_region:raise ValueError('Choose a different receiving region')
    remaining=sum(x['region']==r['region'] and x['type']==r['type'] and x['status']=='available' for x in state['resources'])-1
    if remaining<reserve:raise ValueError(f'Transfer would breach the donor reserve of {reserve}')
    target=REGION_BY_ID[to_region];origin=r['position'];dest=[target['lon'],target['lat']]
    island=REGION_BY_ID[r['region']]['terrain']=='island' or target['terrain']=='island'
    if island and state['conditions']['weather']=='severe':raise ValueError('Simulated sea transfer is unavailable in severe weather')
    mode='sea' if island else 'road';km=distance(origin,dest)*(1 if island else 1.3)
    duration=30+km/(25 if island else 50)*60
    tr=dict(id=f"T{len(state['transfers'])+1:03d}",resource_id=r['id'],from_region=r['region'],to_region=to_region,
        origin=origin,destination=dest,mode=mode,started_at=state['now'],arrival_at=state['now']+duration,status='transferring',
        source='Estimated regional transfer link; not turn-by-turn routing',distance_km=round(km,1))
    state['transfers'].append(tr);r.update(status='transferring',assignment=tr['id'],available_at=tr['arrival_at'])
    emit(state,'transfer',f"{r['id']} mobilised for {target['name']} · estimated {duration:.0f} min")
    state['revision']+=1
    return tr

def stats(values):
    vals=sorted(values)
    return dict(mean=round(statistics.mean(vals),2),p90=round(vals[max(0,math.ceil(.9*len(vals))-1)],2),maximum=round(max(vals),2),count=len(vals)) if vals else dict(mean=None,p90=None,maximum=None,count=0)

def metrics(state):
    incs={i['id']:i for i in state['incidents'] if i['reported_at']<=state['now']}
    patients=[p for p in state['patients'] if p['incident_id'] in incs]
    treated=[p for p in patients if p['treatment_at'] is not None]
    response=[i['first_response']-i['reported_at'] for i in incs.values() if i['first_response'] is not None]
    care=[p['treatment_at']-incs[p['incident_id']]['occurred_at'] for p in treated]
    missions={m.get('patient_id'):m for m in state['missions'] if m['type']=='patient'}
    breakdown=[]
    for p in treated:
        i=incs[p['incident_id']];m=missions[p['id']]
        breakdown.append([i['reported_at']-i['occurred_at'],m['started_at']-i['reported_at'],m['response_at']-m['started_at'],m['depart_at']-m['response_at'],m['arrival_at']-m['depart_at'],m['treatment_at']-m['arrival_at']])
    labels=['Detection','Resource wait','Response travel','Rescue / scene','Transport','Hospital queue']
    used=[r for r in state['resources'] if r['busy_minutes']>0]
    return dict(incidents=len(incs),patients=len(patients),treated=len(treated),unserved=len(patients)-len(treated),
        waiting=sum(p['status']=='waiting' for p in patients),active=sum(p['status'] not in ('waiting','completed') for p in patients),
        evacuated=sum(i['evacuated'] for i in incs.values()),evacuation_demand=sum(i['evacuees'] for i in incs.values()),
        response=stats(response),time_to_care=stats(care),
        hospital_wait=stats([missions[p['id']]['treatment_at']-missions[p['id']]['arrival_at'] for p in treated]),
        bottlenecks=[dict(stage=label,minutes=round(statistics.mean(row[j] for row in breakdown),2) if breakdown else 0) for j,label in enumerate(labels)],
        by_severity={sev:dict(total=sum(p['severity']==sev for p in patients),treated=sum(p['severity']==sev for p in treated),time_to_care=stats([p['treatment_at']-incs[p['incident_id']]['occurred_at'] for p in treated if p['severity']==sev])) for sev in ['critical','serious','minor']},
        utilisation=round(100*sum(r['busy_minutes'] for r in used)/(len(used)*state['now']),1) if used and state['now'] else 0,
        utilisation_denominator='Resources used at least once during this run',
        total_distance_km=round(sum((m.get('route') or m.get('response_route'))['km']+(m.get('transport_route') or m.get('transfer_route') or {}).get('km',0) for m in state['missions']),2))

def snapshot(state):
    s=copy.deepcopy(state);s['metrics']=metrics(state)
    s['events']=s['events'][-160:]
    for f in s['facilities']:
        f['occupied']=(f['baseline_occupied'] if s['now']<f['baseline_release'] else 0)+sum(r['start']<=s['now']<r['end'] for r in f['reservations']) if f['kind']=='hospital' else f['shelter_occupied']
        f['incoming']=sum(r['start']>s['now'] for r in f['reservations']) if f['kind']=='hospital' else f['shelter_reserved']
    for i in s['incidents']:
        ps=[p for p in s['patients'] if p['incident_id']==i['id']]
        i['status']='scheduled' if i['reported_at']>s['now'] else ('resolved' if all(p['status']=='completed' for p in ps) and i['evacuated']==i['evacuees'] else ('responding' if i['rescue_status']!='waiting' else 'awaiting'))
        i['waiting_minutes']=round(max(0,s['now']-i['reported_at']),1)
    return s
