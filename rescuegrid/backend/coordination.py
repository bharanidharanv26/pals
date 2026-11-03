from ortools.sat.python import cp_model
from .catalog import REGION_BY_ID,RESOURCE_TYPES
from .routing import distance
from .planner import solve

def placement(state,region,kind,desired,reserve):
    if region not in REGION_BY_ID or kind not in RESOURCE_TYPES:raise ValueError('Unknown region or resource type')
    available=[r for r in state['resources'] if r['status']=='available' and r['type']==kind]
    existing=sum(r['region']==region for r in available);need=max(0,desired-existing)
    candidates=[];dest=REGION_BY_ID[region]
    for r in available:
        if r['region']==region:continue
        sea=REGION_BY_ID[r['region']]['terrain']=='island' or dest['terrain']=='island'
        if sea and state['conditions']['weather']=='severe':continue
        km=distance(r['position'],[dest['lon'],dest['lat']])*(1 if sea else 1.3)
        candidates.append(dict(resource_id=r['id'],from_region=r['region'],minutes=30+km/(25 if sea else 50)*60,mode='sea' if sea else 'road'))
    model=cp_model.CpModel();xs=[model.NewBoolVar(f'x{j}') for j in range(len(candidates))]
    model.Add(sum(xs)<=need)
    for donor in {r['region'] for r in available}:
        spare=max(0,sum(r['region']==donor for r in available)-reserve)
        model.Add(sum(x for x,c in zip(xs,candidates) if c['from_region']==donor)<=spare)
    model.Minimize(sum(x*(int(c['minutes'])-1_000_000) for x,c in zip(xs,candidates)))
    solver,status=solve(model)
    chosen=[c for x,c in zip(xs,candidates) if solver.Value(x)] if status in (cp_model.OPTIMAL,cp_model.FEASIBLE) else []
    return dict(revision=state['revision'],region=region,type=kind,requested=desired,existing=existing,unmet=max(0,need-len(chosen)),reserve=reserve,assignments=chosen,solver_status=solver.StatusName(status))
