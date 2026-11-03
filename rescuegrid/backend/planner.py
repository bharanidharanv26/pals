"""Staged rescue assignment followed by a capacitated patient-care schedule.

CP-SAT optimality applies to the current candidate model, not the nationwide future.
Time is discretised to minutes. Resource commitments are hard constraints.
"""
from __future__ import annotations
import math
import time
from ortools.sat.python import cp_model
from .catalog import HAZARDS, SEVERITY
from .routing import route, network, node_position

def solve(model, budget=.8):
    solver=cp_model.CpSolver()
    solver.parameters.num_search_workers=1
    solver.parameters.random_seed=0
    solver.parameters.max_deterministic_time=budget
    solver.parameters.max_time_in_seconds=3
    status=solver.Solve(model)
    return solver,status

def occupied_intervals(f,now):
    rows=[(r['start'],r['end']) for r in f['reservations'] if r['end']>now]
    if f['baseline_release']>now:
        rows += [(now,f['baseline_release'])]*f['baseline_occupied']
    return rows

def next_slot(f,arrival,duration,extra=None):
    intervals=occupied_intervals(f,0)+(extra or [])
    points=sorted(set([arrival]+[b for a,b in intervals if b>=arrival]))
    for start in points:
        end=start+duration
        cuts=sorted(set([start,end]+[x for ab in intervals for x in ab if start<x<end]))
        if all(sum(a<=((l+r)/2)<b for a,b in intervals)<f['capacity'] for l,r in zip(cuts,cuts[1:])):
            return start
    return max([arrival]+[b for a,b in intervals])

def build_plan(state,policy='optimized'):
    begun=time.perf_counter()
    now=state['now']
    conditions=state['conditions']
    active=[i for i in state['incidents'] if i['reported_at']<=now]
    incs={i['id']:i for i in active}
    available=[r for r in state['resources'] if r['status']=='available']
    facilities=[f for f in state['facilities'] if not f['closed']]
    rescues=[]; assignments=[]; evacuations=[]; unassigned=[]
    solver_states=[]
    rescue_candidates=[]
    for inc in active:
        if inc['rescue_status']!='waiting': continue
        h=HAZARDS[inc['hazard']]
        for r in available:
            air_rescue=r['type']=='helicopter' and inc['hazard'] in ('landslide','flood','tsunami')
            if r['region']!=inc['region'] or (r['type']!=h['rescue'] and not air_rescue): continue
            mode='air' if air_rescue else h['mode']
            path=route(inc['region'],r['node'],inc['node'],conditions,mode)
            if not path: continue
            # Flood evacuation requires repeated boat trips; includes the entire group.
            trip_factor=math.ceil((len(inc['patients'])+inc['evacuees'])/r['capacity']) if mode in ('water','air') else 1
            duration=inc['rescue_duration']
            pickup=str(list(network(inc['region']).nodes)[len(network(inc['region']))//2]) if mode in ('water','air') else inc['node']
            return_leg=route(inc['region'],inc['node'],pickup,conditions,mode) if mode in ('water','air') else None
            if mode in ('water','air') and return_leg is None: continue
            if return_leg:duration+=max(0,trip_factor-1)*(2*return_leg['minutes']+4)
            ready=now+path['minutes']+duration+(return_leg['minutes'] if return_leg else 0)
            medical_ready=ready
            if return_leg and inc['patients']:
                medical_trips=math.ceil(len(inc['patients'])/r['capacity'])
                medical_ready=now+path['minutes']+inc['rescue_duration']+max(0,medical_trips-1)*(2*return_leg['minutes']+4)+return_leg['minutes']
            rescue_candidates.append(dict(incident_id=inc['id'],resource_id=r['id'],route=path,transfer_route=return_leg,
                response_at=now+path['minutes'],ready_at=medical_ready,evac_ready_at=ready,available_at=ready+5,pickup_node=pickup,
                duration=duration,steps=['Air access','Hoist rescue','Transfer to ground medical transport'] if air_rescue else h['steps'],type='rescue'))
    if policy=='optimized' and rescue_candidates:
        m=cp_model.CpModel(); xs=[m.NewBoolVar(f'r{j}') for j in range(len(rescue_candidates))]
        for iid in {c['incident_id'] for c in rescue_candidates}:
            m.Add(sum(x for x,c in zip(xs,rescue_candidates) if c['incident_id']==iid)<=1)
        for rid in {c['resource_id'] for c in rescue_candidates}:
            m.Add(sum(x for x,c in zip(xs,rescue_candidates) if c['resource_id']==rid)<=1)
        m.Minimize(sum(x*(int(c['ready_at']-now)*SEVERITY[incs[c['incident_id']]['severity']]-10000*SEVERITY[incs[c['incident_id']]['severity']]) for x,c in zip(xs,rescue_candidates)))
        s,status=solve(m)
        solver_states.append(s.StatusName(status))
        if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            rescues=[c for x,c in zip(xs,rescue_candidates) if s.Value(x)]
    if policy!='optimized' or (rescue_candidates and not rescues):
        used=set(); done=set()
        candidates=sorted(rescue_candidates,key=lambda c:(-SEVERITY[incs[c['incident_id']]['severity']] if policy!='nearest' else incs[c['incident_id']]['reported_at'],c['response_at'],c['incident_id']))
        for c in candidates:
            if c['resource_id'] not in used and c['incident_id'] not in done:
                rescues.append(c); used.add(c['resource_id']);done.add(c['incident_id'])
    rescue_map={c['incident_id']:c for c in rescues}
    for i in active:
        if i['rescue_status'] in ('active','completed'):
            rescue_map[i['id']]=dict(ready_at=i['rescue_ready'],evac_ready_at=i.get('evac_ready_at',i['rescue_ready']),pickup_node=i.get('pickup_node',i['node']))
    pending=[p for p in state['patients'] if p['status']=='waiting' and p['incident_id'] in incs]
    pending.sort(key=lambda p:(-(SEVERITY[p['severity']]+(now-incs[p['incident_id']]['reported_at'])/30),p['id']))
    candidates=[]
    for p in pending[:60]:
        inc=incs[p['incident_id']]
        rescue=rescue_map.get(inc['id'])
        if not rescue:
            unassigned.append(dict(patient_id=p['id'],reason=f"No available, reachable {HAZARDS[inc['hazard']]['rescue'].replace('_',' ')}"));continue
        pickup=rescue['pickup_node']
        vehicles=[]
        for r in available:
            if r['region']!=inc['region'] or r['type'] not in ('als','bls') or (p['severity']=='critical' and r['type']!='als'):continue
            response=route(inc['region'],r['node'],pickup,conditions)
            if response:vehicles.append((r,response))
        hospitals=[]
        for f in facilities:
            if f['kind']!='hospital' or f['region']!=inc['region'] or p['care'] not in f['capabilities']:continue
            travel=route(inc['region'],pickup,f['node'],conditions)
            if travel:hospitals.append((f,travel))
        for r,response in sorted(vehicles,key=lambda row:row[1]['minutes'])[:6]:
            for f,travel in hospitals:
                depart=max(now+response['minutes'],rescue['ready_at'])+p['scene_duration']
                arrival=depart+travel['minutes']
                earliest=next_slot(f,arrival,p['treatment_duration'])
                candidates.append(dict(type='patient',patient_id=p['id'],incident_id=inc['id'],resource_id=r['id'],facility_id=f['id'],
                    response_route=response,transport_route=travel,response_at=now+response['minutes'],depart_at=depart,arrival_at=arrival,
                    treatment_at=earliest,duration=p['treatment_duration'],severity=p['severity'],pickup_node=pickup,
                    available_at=arrival+9,score=earliest,explanation=[f"{r['type'].upper()} capability matches {p['severity']} patient",f"Receiving facility supports {p['care']} care",'Rescue prerequisites complete before patient departure']))
        if not vehicles or not hospitals:
            unassigned.append(dict(patient_id=p['id'],reason='No available suitable ambulance' if not vehicles else 'No reachable, open facility with required care'))
    # The optional intervals enforce real bay capacity across all simultaneous assignments.
    if policy=='optimized' and candidates:
        m=cp_model.CpModel(); xs=[]; starts=[]; intervals={f['id']:[] for f in facilities if f['kind']=='hospital'}
        horizon=int(now)+1440
        for f in facilities:
            if f['kind']!='hospital':continue
            for k,(a,b) in enumerate(occupied_intervals(f,now)):
                a,b=math.floor(a),math.ceil(b)
                intervals[f['id']].append(m.NewIntervalVar(a,b-a,b,f"existing{f['id']}-{k}"))
        objective=[]
        for j,c in enumerate(candidates):
            x=m.NewBoolVar(f'x{j}');start=m.NewIntVar(0,horizon,f's{j}');end=m.NewIntVar(0,horizon+60,f'e{j}')
            m.Add(start>=math.ceil(c['arrival_at'])).OnlyEnforceIf(x)
            m.Add(start==0).OnlyEnforceIf(x.Not())
            interval=m.NewOptionalIntervalVar(start,c['duration'],end,x,f'i{j}')
            intervals[c['facility_id']].append(interval)
            xs.append(x);starts.append(start)
            waiting=now-incs[c['incident_id']]['reported_at']
            weight=SEVERITY[c['severity']]+int(waiting/15)
            objective.extend([start*weight*10,x*(-100000*weight+int(c['response_route']['km']+c['transport_route']['km']))])
        for pid in {c['patient_id'] for c in candidates}:
            m.Add(sum(x for x,c in zip(xs,candidates) if c['patient_id']==pid)<=1)
        for rid in {c['resource_id'] for c in candidates}:
            m.Add(sum(x for x,c in zip(xs,candidates) if c['resource_id']==rid)<=1)
        for f in facilities:
            if f['kind']=='hospital' and intervals[f['id']]:m.AddCumulative(intervals[f['id']],[1]*len(intervals[f['id']]),f['capacity'])
        m.Minimize(sum(objective))
        s,status=solve(m)
        solver_states.append(s.StatusName(status))
        if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            for x,start,c in zip(xs,starts,candidates):
                if s.Value(x):
                    c['treatment_at']=float(s.Value(start));c['available_at']=c['treatment_at']+9;assignments.append(c)
    if policy!='optimized' or (candidates and not assignments):
        used=set();extra={}
        order=sorted(pending,key=lambda p:(incs[p['incident_id']]['reported_at'] if policy=='nearest' else -SEVERITY[p['severity']],p['id']))
        for p in order:
            options=[]
            for c in candidates:
                if c['patient_id']!=p['id'] or c['resource_id'] in used:continue
                f=next(f for f in facilities if f['id']==c['facility_id'])
                c['treatment_at']=next_slot(f,c['arrival_at'],c['duration'],extra.get(f['id'],[]))
                options.append(c)
            if not options:continue
            c=min(options,key=lambda c:(c['response_route']['minutes'],c['transport_route']['minutes'],c['resource_id'],c['facility_id']))
            c['available_at']=c['treatment_at']+9
            assignments.append(c);used.add(c['resource_id']);extra.setdefault(c['facility_id'],[]).append((c['treatment_at'],c['treatment_at']+c['duration']))
    assigned={c['patient_id'] for c in assignments}
    known={u['patient_id'] for u in unassigned}
    for p in pending:
        if p['id'] not in assigned and p['id'] not in known:
            unassigned.append(dict(patient_id=p['id'],reason='Resources committed to higher-priority demand; queued for next cycle'))
    used_buses=set();shelter_space={f['id']:f['capacity']-f['shelter_occupied']-f['shelter_reserved'] for f in facilities if f['kind']=='shelter'}
    for inc in active:
        remaining=inc['evacuees']-inc['evacuated']-inc['evac_reserved']
        rescue=rescue_map.get(inc['id'])
        if remaining<=0 or not rescue:continue
        for r in available:
            if remaining<=0:break
            if r['type']!='bus' or r['region']!=inc['region'] or r['id'] in used_buses:continue
            pickup=rescue['pickup_node'];response=route(inc['region'],r['node'],pickup,conditions)
            if not response:continue
            options=[]
            for f in facilities:
                if f['kind']!='shelter' or f['region']!=inc['region'] or shelter_space[f['id']]<=0:continue
                travel=route(inc['region'],pickup,f['node'],conditions)
                if travel:options.append((f,travel))
            if not options:break
            f,travel=min(options,key=lambda ft:ft[1]['minutes'])
            size=min(r['capacity'],remaining,shelter_space[f['id']])
            depart=max(now+response['minutes'],rescue.get('evac_ready_at',rescue['ready_at']))+5
            arrival=depart+travel['minutes']
            evacuations.append(dict(type='evacuation',incident_id=inc['id'],resource_id=r['id'],facility_id=f['id'],people=size,pickup_node=pickup,
                response_route=response,transport_route=travel,response_at=now+response['minutes'],depart_at=depart,arrival_at=arrival,available_at=arrival+8))
            remaining-=size;shelter_space[f['id']]-=size;used_buses.add(r['id'])
    for a in assignments:
        a['explanation'].append(f"Predicted treatment queue: {max(0,a['treatment_at']-a['arrival_at']):.1f} min")
    return dict(revision=state['revision'],at=now,policy=policy,rescues=rescues,assignments=assignments,evacuations=evacuations,
                unassigned=unassigned,solver_status=' / '.join(solver_states) if solver_states else 'HEURISTIC',
                model='Staged rescue allocation + CP-SAT patient/bay scheduling' if policy=='optimized' else 'Capability-constrained greedy dispatch',
                runtime_ms=round((time.perf_counter()-begun)*1000,1),candidate_count=len(candidates))
