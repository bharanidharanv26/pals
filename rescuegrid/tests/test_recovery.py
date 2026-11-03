import copy
import uuid
from fastapi.testclient import TestClient
from backend.app import app
from backend import store,experiments

client=TestClient(app)

def job_record(status='queued',owner='recovery-test'):
    job=dict(id=uuid.uuid4().hex,owner=owner,status=status,progress=0,config={},result=None)
    store.save(job['id'],'experiment',job,owner)
    return job

def test_health_identifies_the_actual_running_process():
    import os
    health=client.get('/api/health').json()
    assert health['service']=='rescuegrid-india'
    assert health['pid']==os.getpid()
    assert len(health['instance_id'])==32

def test_old_playback_revision_cannot_advance_twice():
    state=client.post('/api/sessions',json={'preset':'heatwave','count':1}).json()
    headers={'X-Session-ID':state['id']}
    request=dict(minutes=5,expected_revision=state['revision'])
    first=client.post('/api/advance',json=request,headers=headers)
    assert first.status_code==200 and first.json()['now']==5
    repeated=client.post('/api/advance',json=request,headers=headers)
    assert repeated.status_code==409
    assert client.get('/api/state',headers=headers).json()['now']==5

def test_cancelled_queued_experiment_never_starts(monkeypatch):
    job=job_record()
    assert store.cancel_experiment(job['id'],job['owner'])=='cancelled'
    def unexpected(*args,**kwargs):
        raise AssertionError('A cancelled job must not allocate a simulation')
    monkeypatch.setattr(experiments,'create_world',unexpected)
    experiments.run_job(copy.deepcopy(job))
    assert store.load(job['id'])['status']=='cancelled'

def test_late_worker_cannot_overwrite_cancellation_or_completed_results():
    job=job_record('running')
    stale=copy.deepcopy(job)
    store.cancel_experiment(job['id'],job['owner'])
    stale.update(status='completed',progress=100)
    assert not store.update_experiment(stale)
    assert store.load(job['id'])['status']=='cancelled'
    complete=job_record('completed')
    assert store.cancel_experiment(complete['id'],complete['owner'])=='completed'

def test_restart_marks_unfinished_jobs_and_preserves_workspace():
    state=client.post('/api/sessions',json={'preset':'chennai','count':1}).json()
    headers={'X-Session-ID':state['id']}
    saved=client.post('/api/advance',json={'minutes':5},headers=headers).json()
    queued=job_record('queued',state['id'])
    running=job_record('running',state['id'])
    completed=job_record('completed',state['id'])
    store.recover_interrupted_experiments()
    assert store.load(queued['id'])['status']=='interrupted'
    assert store.load(running['id'])['status']=='interrupted'
    assert store.load(completed['id'])['status']=='completed'
    current=client.get('/api/state',headers=headers).json()
    assert current['now']==saved['now'] and current['id']==saved['id']
    assert current['missions']==saved['missions']
    assert not store.update_experiment({**running,'status':'completed'})
