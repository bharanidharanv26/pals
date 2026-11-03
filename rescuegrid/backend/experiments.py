from __future__ import annotations
import math
import statistics
import uuid
import threading
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timezone
from . import store
from .scenarios import create_world
from .engine import advance,metrics,snapshot

pool=ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'))
queue_slots=threading.BoundedSemaphore(4)

def run_job(job):
    try:
        job['status']='running'
        if not store.update_experiment(job,allowed=('queued',)):return
        config=job['config'];results={k:[] for k in ['nearest','priority','optimized']};histories={};traces={}
        total=config['repetitions']*3;done=0
        for repeat in range(config['repetitions']):
            for policy in results:
                if store.load(job['id'])['status']!='running':return
                state=create_world(config['preset'],config['seed']+repeat,config.get('region'),config.get('hazard'),config.get('count'),config.get('extra_ambulances',0))
                state['conditions']['traffic']=config['traffic']
                history=[dict(minute=0,treated=0,unserved=0)]
                for _ in range(math.ceil(config['horizon']/15)):
                    if store.load(job['id'])['status']!='running':return
                    advance(state,min(15,config['horizon']-state['now']),policy,True)
                    met=metrics(state);history.append(dict(minute=state['now'],treated=met['treated'],unserved=met['unserved']))
                met=metrics(state);results[policy].append(met)
                if repeat==0:
                    histories[policy]=history
                    # Save complete event records for reproducible inspection, with bounded snapshots for replay.
                    traces[policy]=dict(events=state['events'],missions=state['missions'],metrics=met,decisions=state['decisions'],data_versions=state['data_versions'])
                done+=1;job['progress']=round(done/total*100)
                if not store.update_experiment(job,allowed=('running',)):return
        aggregate={}
        for policy,rows in results.items():
            care=[r['time_to_care']['mean'] for r in rows if r['time_to_care']['mean'] is not None]
            critical=[r['by_severity']['critical']['time_to_care']['mean'] for r in rows if r['by_severity']['critical']['time_to_care']['mean'] is not None]
            aggregate[policy]=dict(time_to_care=statistics.mean(care) if care else None,
                critical_care_minutes=statistics.mean(critical) if critical else None,
                response=statistics.mean(r['response']['mean'] or 0 for r in rows),
                treated=statistics.mean(r['treated'] for r in rows),unserved=statistics.mean(r['unserved'] for r in rows),
                evacuated=statistics.mean(r['evacuated'] for r in rows),hospital_wait=statistics.mean(r['hospital_wait']['mean'] or 0 for r in rows),
                p90_care=statistics.mean(r['time_to_care']['p90'] or 0 for r in rows),
                distance_km=statistics.mean(r['total_distance_km'] for r in rows),bottlenecks=rows[0]['bottlenecks'],by_severity=rows[0]['by_severity'])
        paired=[a['time_to_care']['mean']-b['time_to_care']['mean'] for a,b in zip(results['nearest'],results['optimized']) if a['time_to_care']['mean'] is not None and b['time_to_care']['mean'] is not None]
        diff=statistics.mean(paired) if paired else None
        ci=1.96*statistics.stdev(paired)/math.sqrt(len(paired)) if len(paired)>1 else None
        if store.load(job['id'])['status']!='running':return
        job.update(status='completed',progress=100,result=dict(aggregate=aggregate,replicates=results,histories=histories,
            paired_difference_minutes=diff,normal_approximation_95ci=[diff-ci,diff+ci] if ci is not None else None,
            note='Care-time means describe treated patients. Compare unmet demand alongside time metrics. CI uses paired run means and a normal approximation.'),traces=traces,
            reproducibility=dict(engine='RescueGrid 1.0',seeds=[config['seed']+i for i in range(config['repetitions'])],solver='CP-SAT single worker, deterministic budget; 3 s wall guard',data='Versioned local network packages; synthetic operational data'))
        store.update_experiment(job,allowed=('running',))
    except Exception as exc:
        job.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        store.update_experiment(job)

def submit(owner,config):
    ongoing=[j for j in store.listing('experiment',owner) if j['status'] in ('queued','running')]
    if ongoing:raise ValueError('An experiment is already running in this workspace')
    if not queue_slots.acquire(blocking=False):raise ValueError('The experiment worker queue is full. Try again when a running job finishes.')
    job=dict(id=uuid.uuid4().hex,owner=owner,config=config,status='queued',progress=0,created_at=datetime.now(timezone.utc).isoformat(),result=None)
    try:
        store.save(job['id'],'experiment',job,owner)
        future=pool.submit(run_job,job)
        def finished(f):
            queue_slots.release()
            if not f.cancelled() and f.exception():
                latest=store.load(job['id']) or job
                latest.update(status='failed',error=str(f.exception()))
                store.update_experiment(latest)
        future.add_done_callback(finished)
    except Exception:
        queue_slots.release();raise
    return job
