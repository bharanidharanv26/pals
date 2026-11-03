from __future__ import annotations
import asyncio
import csv
import io
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI,HTTPException,Header,Request
from fastapi.responses import FileResponse,StreamingResponse,Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel,Field,model_validator
from .catalog import REGIONS,REGION_BY_ID,HAZARDS,RESOURCE_TYPES,PRESETS,ASSUMPTIONS
from .routing import network,network_geojson,nearest,distance
from .scenarios import create_world,add_incident
from .planner import build_plan
from .engine import snapshot,commit,advance,emit,close_corridor,transfer
from . import store,experiments,alerts,coordination

ROOT=Path(__file__).resolve().parents[1]
INSTANCE_ID=uuid.uuid4().hex

@asynccontextmanager
async def lifespan(application):
    # A stopped process cannot finish its old jobs; keep results and workspaces intact.
    await asyncio.to_thread(store.recover_interrupted_experiments)
    yield

app=FastAPI(title='RescueGrid Chennai',version='1.1.0',lifespan=lifespan,description='Chennai multi-hazard response simulation. Synthetic operational data.')
app.add_middleware(GZipMiddleware,minimum_size=1000)

class ScenarioInput(BaseModel):
    preset:str='chennai_city'
    seed:int=Field(default=42,ge=0,le=2**31-1)
    region:str|None=None
    hazard:str|None=None
    count:int|None=Field(default=None,ge=1,le=20)
    extra_ambulances:int=Field(default=0,ge=0,le=5)
    @model_validator(mode='after')
    def validate_catalog(self):
        if self.preset not in {p['id'] for p in PRESETS}:raise ValueError('Unknown scenario')
        if self.region and self.region!='ALL' and self.region not in REGION_BY_ID:raise ValueError('Unknown region')
        if self.hazard and self.hazard!='mixed' and self.hazard not in HAZARDS:raise ValueError('Unknown hazard')
        return self

class IncidentInput(BaseModel):
    region:str
    hazard:str
    severity:Literal['critical','serious','minor']='serious'
    patients:int=Field(default=2,ge=0,le=20)
    evacuees:int=Field(default=0,ge=0,le=100)
    title:str|None=Field(default=None,max_length=120)
    longitude:float|None=Field(default=None,ge=79.9,le=80.4)
    latitude:float|None=Field(default=None,ge=12.8,le=13.35)
    @model_validator(mode='after')
    def valid(self):
        if self.region not in REGION_BY_ID or self.hazard not in HAZARDS:raise ValueError('Unknown region or disaster')
        if self.patients+self.evacuees==0:raise ValueError('Enter at least one patient or evacuee')
        if (self.longitude is None)!=(self.latitude is None):raise ValueError('Enter both coordinates')
        return self

class StepInput(BaseModel):
    minutes:float=Field(default=5,ge=.1,le=120)
    auto:bool=True
    policy:Literal['nearest','priority','optimized']='optimized'
    expected_revision:int|None=Field(default=None,ge=0)
class PlanInput(BaseModel):
    policy:Literal['nearest','priority','optimized']='optimized'
class CommitInput(BaseModel):
    plan_id:str
class ConditionsInput(BaseModel):
    traffic:float|None=Field(default=None,ge=.7,le=4)
    weather:Literal['normal','severe']|None=None
    close_region:str|None=None
    clear_roads:bool=False
class FacilityInput(BaseModel):
    closed:bool|None=None
    capacity:int|None=Field(default=None,ge=1,le=500)
class ResourceInput(BaseModel):
    offline:bool
class TransferInput(BaseModel):
    resource_id:str
    to_region:str
    reserve:int=Field(default=1,ge=0,le=10)
class ExperimentInput(ScenarioInput):
    repetitions:int=Field(default=1,ge=1,le=30)
    horizon:int=Field(default=180,ge=30,le=360)
    traffic:float=Field(default=1.35,ge=.7,le=4)
class CapInput(BaseModel):
    xml:str=Field(min_length=20,max_length=100000)
class PlacementInput(BaseModel):
    region:str
    type:str
    desired:int=Field(default=4,ge=1,le=20)
    reserve:int=Field(default=1,ge=0,le=10)

def require_session(sid):
    if not sid or len(sid)!=32 or any(c not in '0123456789abcdef' for c in sid):raise HTTPException(401,'Create a workspace first')
    s=store.load(sid,'session')
    if not s:raise HTTPException(401,'Workspace expired or not found')
    return s

def change(sid,fn):
    with store.lock(sid):
        s=require_session(sid)
        try:result=fn(s)
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc
        store.save(sid,'session',s,sid)
        return result if result is not None else snapshot(s)

@app.get('/api/health')
def health():return dict(status='ok',version='1.1.0',service='rescuegrid-chennai',pid=os.getpid(),instance_id=INSTANCE_ID)

@app.get('/api/catalog')
def catalog():
    sources=[]
    path=ROOT/'data'/'geography'/'sources.json'
    if path.exists():sources=json.loads(path.read_text(encoding='utf-8'))
    return dict(regions=REGIONS,hazards=HAZARDS,resource_types=RESOURCE_TYPES,presets=PRESETS,assumptions=ASSUMPTIONS,sources=sources,
        networks=[dict(region=r['id'],source=network(r['id']).graph['source'],mode=network(r['id']).graph['mode'],nodes=len(network(r['id']))) for r in REGIONS])

@app.post('/api/sessions')
def new_session(body:ScenarioInput):
    s=create_world(**body.model_dump());s['id']=uuid.uuid4().hex
    emit(s,'system','Workspace created. Operational data is simulated.')
    store.save(s['id'],'session',s,s['id'])
    return snapshot(s)

@app.get('/api/state')
def get_state(x_session_id:str|None=Header(default=None)):
    return snapshot(require_session(x_session_id))

@app.post('/api/reset')
def reset(body:ScenarioInput,x_session_id:str|None=Header(default=None)):
    with store.lock(x_session_id):
        old=require_session(x_session_id);s=create_world(**body.model_dump());s['id']=old['id'];s['revision']=old['revision']+1
        emit(s,'system','Scenario loaded. Clock reset to 00:00.')
        store.save(s['id'],'session',s,s['id']);return snapshot(s)

@app.post('/api/incidents')
def incident(body:IncidentInput,x_session_id:str|None=Header(default=None)):
    def action(s):
        if len(s['incidents'])>=80:raise ValueError('This workspace supports up to 80 incidents. Reset to begin a new exercise.')
        node=None
        if body.longitude is not None:
            point=[body.longitude,body.latitude];node=nearest(body.region,point)
            if distance(point,network(body.region).nodes[node]['pos'])>5:raise ValueError('Location is more than 5 km from the Chennai road network. Choose a point inside Chennai.')
        inc=add_incident(s,body.region,body.hazard,body.severity,body.patients,body.evacuees,body.title,node)
        emit(s,'incident',f"New incident: {inc['title']}",inc['id']);s['revision']+=1
    return change(x_session_id,action)

@app.post('/api/plans')
def plan(body:PlanInput,x_session_id:str|None=Header(default=None)):
    with store.lock(x_session_id):
        s=require_session(x_session_id);p=build_plan(s,body.policy);p['id']=uuid.uuid4().hex
        store.save(p['id'],'plan',p,x_session_id);return p

@app.post('/api/plans/commit')
def apply_plan(body:CommitInput,x_session_id:str|None=Header(default=None)):
    def action(s):
        p=store.load(body.plan_id,'plan',x_session_id)
        if not p:raise ValueError('Plan not found in this workspace')
        commit(s,p)
    return change(x_session_id,action)

@app.post('/api/advance')
def step(body:StepInput,x_session_id:str|None=Header(default=None)):
    def action(s):
        if body.expected_revision is not None and body.expected_revision!=s['revision']:
            raise ValueError('The workspace changed. Refresh the saved state before advancing again.')
        if s['now']+body.minutes>1440:raise ValueError('Exercise horizon is 24 hours. Save and reset for another run.')
        s['settings']['policy']=body.policy
        advance(s,body.minutes,body.policy,body.auto)
    return change(x_session_id,action)

@app.patch('/api/conditions')
def conditions(body:ConditionsInput,x_session_id:str|None=Header(default=None)):
    def action(s):
        if body.close_region:
            if body.close_region not in REGION_BY_ID:raise ValueError('Unknown region')
            close_corridor(s,body.close_region)
        if body.clear_roads:s['conditions']['closed_edges']={}
        if body.traffic is not None:s['conditions']['traffic']=body.traffic
        if body.weather is not None:s['conditions']['weather']=body.weather
        s['revision']+=1;emit(s,'disruption','Operating conditions updated; pending plans require recalculation.')
    return change(x_session_id,action)

@app.patch('/api/facilities/{fid}')
def facility(fid:str,body:FacilityInput,x_session_id:str|None=Header(default=None)):
    def action(s):
        f=next((f for f in s['facilities'] if f['id']==fid),None)
        if not f:raise ValueError('Facility not found')
        if body.capacity is not None:
            # Existing capacity reservations are commitments; increasing capacity is always valid.
            reserved=max([f['baseline_occupied']]+[sum(r['start']<=t<r['end'] for r in f['reservations'])+(f['baseline_occupied'] if t<f['baseline_release'] else 0) for t in [s['now']]+[r['start'] for r in f['reservations']]]) if f['kind']=='hospital' else f['shelter_occupied']+f['shelter_reserved']
            if body.capacity<reserved:raise ValueError(f'Capacity cannot be below {reserved} committed places. Close new admissions instead.')
            f['capacity']=body.capacity
        if body.closed is not None:f['closed']=body.closed
        s['revision']+=1;emit(s,'facility',f"{fid}: facility availability updated")
    return change(x_session_id,action)

@app.patch('/api/resources/{rid}')
def resource(rid:str,body:ResourceInput,x_session_id:str|None=Header(default=None)):
    def action(s):
        r=next((r for r in s['resources'] if r['id']==rid),None)
        if not r:raise ValueError('Resource not found')
        if r['status'] not in ('available','offline'):raise ValueError('This resource is committed to an active mission')
        r['status']='offline' if body.offline else 'available';s['revision']+=1
        emit(s,'resource',f"{rid}: {r['status']}")
    return change(x_session_id,action)

@app.post('/api/transfers')
def mutual_aid(body:TransferInput,x_session_id:str|None=Header(default=None)):
    def action(s):
        if body.to_region not in REGION_BY_ID:raise ValueError('Unknown receiving region')
        transfer(s,body.resource_id,body.to_region,body.reserve)
    return change(x_session_id,action)

@app.get('/api/networks/{region}')
def geo_network(region:str):
    if region not in REGION_BY_ID:raise HTTPException(404,'Region not found')
    return network_geojson(region)

@app.post('/api/preposition')
def preposition(body:PlacementInput,x_session_id:str|None=Header(default=None)):
    with store.lock(x_session_id):
        s=require_session(x_session_id)
        try:p=coordination.placement(s,body.region,body.type,body.desired,body.reserve)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        p['id']=uuid.uuid4().hex;store.save(p['id'],'placement',p,x_session_id);return p

@app.post('/api/preposition/commit')
def commit_placement(body:CommitInput,x_session_id:str|None=Header(default=None)):
    def action(s):
        p=store.load(body.plan_id,'placement',x_session_id)
        if not p or p['revision']!=s['revision']:raise ValueError('State changed. Recalculate the placement.')
        for a in p['assignments']:transfer(s,a['resource_id'],p['region'],p['reserve'])
    return change(x_session_id,action)

@app.get('/api/districts')
def districts(region:str|None=None):
    # Chennai-only reference directory: the operating zones replace the old
    # national district index.
    rows=[dict(id=z['id'],name=z['name'],region=z['id'],position=[z['lon'],z['lat']],year='2026') for z in REGIONS]
    return [r for r in rows if not region or r['region']==region]

@app.post('/api/experiments')
def experiment(body:ExperimentInput,x_session_id:str|None=Header(default=None)):
    require_session(x_session_id)
    try:return experiments.submit(x_session_id,body.model_dump())
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc

@app.get('/api/experiments')
def experiment_list(x_session_id:str|None=Header(default=None)):
    require_session(x_session_id)
    return [{k:v for k,v in j.items() if k!='traces'} for j in store.listing('experiment',x_session_id)]

@app.get('/api/experiments/{jid}')
def experiment_get(jid:str,x_session_id:str|None=Header(default=None)):
    require_session(x_session_id);job=store.load(jid,'experiment',x_session_id)
    if not job:raise HTTPException(404,'Experiment not found')
    return {k:v for k,v in job.items() if k!='traces'}

@app.post('/api/experiments/{jid}/cancel')
def cancel(jid:str,x_session_id:str|None=Header(default=None)):
    require_session(x_session_id);job=store.load(jid,'experiment',x_session_id)
    if not job:raise HTTPException(404,'Experiment not found')
    try:return {'status':store.cancel_experiment(jid,x_session_id)}
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc

@app.get('/api/experiments/{jid}/trace')
def trace(jid:str,policy:Literal['nearest','priority','optimized']='optimized',x_session_id:str|None=Header(default=None)):
    require_session(x_session_id);job=store.load(jid,'experiment',x_session_id)
    if not job or job['status']!='completed':raise HTTPException(404,'Completed experiment not found')
    return job['traces'][policy]

@app.get('/api/export')
def export(kind:Literal['snapshot','events','experiment']='snapshot',job_id:str|None=None,x_session_id:str|None=Header(default=None)):
    s=require_session(x_session_id)
    if kind=='experiment':
        data=store.load(job_id or '','experiment',x_session_id)
        if not data:raise HTTPException(404,'Experiment not found')
    elif kind=='events':
        buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=['id','at','kind','message','incident_id']);writer.writeheader();writer.writerows(s['events'])
        return Response(buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="rescuegrid-events.csv"'})
    else:data=snapshot(s)
    return Response(json.dumps(data,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="rescuegrid-{kind}.json"'})

@app.get('/api/alerts')
def public_alerts(provider:Literal['sachet','earthquakes']='sachet'):
    return alerts.earthquakes() if provider=='earthquakes' else alerts.fetch_alerts()

@app.post('/api/alerts/import')
def cap_import(body:CapInput,x_session_id:str|None=Header(default=None)):
    require_session(x_session_id)
    try:items=alerts.parse_cap(body.xml)
    except Exception as exc:raise HTTPException(422,'Invalid or unsupported CAP/RSS XML') from exc
    store.save(uuid.uuid4().hex,'alert_import',dict(items=items),x_session_id)
    return dict(status='imported',items=items)

@app.get('/api/stream')
async def stream(request:Request,session_id:str):
    require_session(session_id)
    async def events():
        revision=-1
        while not await request.is_disconnected():
            s=await asyncio.to_thread(store.load,session_id,'session')
            if s and s['revision']!=revision:
                revision=s['revision'];yield f"id: {revision}\ndata: {json.dumps({'revision':revision,'now':s['now']})}\n\n"
            else:yield ': heartbeat\n\n'
            await asyncio.sleep(2)
    return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

geography=ROOT/'data'/'geography'
if geography.exists():app.mount('/geography',StaticFiles(directory=geography),name='geography')
dist=ROOT/'frontend'/'dist'
if dist.exists():
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/{path:path}')
    def spa(path:str):
        if path.startswith('api/'):raise HTTPException(404,'API endpoint not found')
        target=(dist/path).resolve()
        if target.is_relative_to(dist.resolve()) and target.is_file():return FileResponse(target)
        return FileResponse(dist/'index.html')
