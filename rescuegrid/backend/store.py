from __future__ import annotations
import json
import os
import threading
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import create_engine,MetaData,Table,Column,String,Text,select,insert,update

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'
RUNTIME.mkdir(exist_ok=True)
URL=os.environ.get('DATABASE_URL') or f"sqlite:///{(RUNTIME/'rescuegrid.db').as_posix()}"
if URL.startswith('postgres://'):URL=URL.replace('postgres://','postgresql+psycopg://',1)
if URL.startswith('postgresql://'):URL=URL.replace('postgresql://','postgresql+psycopg://',1)
db=create_engine(URL,connect_args={'check_same_thread':False,'timeout':30} if URL.startswith('sqlite') else {},pool_pre_ping=True)
metadata=MetaData()
records=Table('records',metadata,Column('id',String(64),primary_key=True),Column('kind',String(24)),Column('owner',String(64)),Column('data',Text),Column('updated_at',String(40)))
metadata.create_all(db)
_locks={};_guard=threading.Lock()

def lock(key):
    with _guard:return _locks.setdefault(key,threading.RLock())

def save(key,kind,data,owner=''):
    payload=dict(kind=kind,owner=owner,data=json.dumps(data,ensure_ascii=False,allow_nan=False),updated_at=datetime.now(timezone.utc).isoformat())
    with db.begin() as conn:
        result=conn.execute(update(records).where(records.c.id==key).values(**payload))
        if not result.rowcount:conn.execute(insert(records).values(id=key,**payload))

def load(key,kind=None,owner=None):
    query=select(records).where(records.c.id==key)
    if kind:query=query.where(records.c.kind==kind)
    if owner:query=query.where(records.c.owner==owner)
    with db.connect() as conn:
        row=conn.execute(query).mappings().first()
    return json.loads(row['data']) if row else None

def listing(kind,owner):
    with db.connect() as conn:
        rows=conn.execute(select(records).where(records.c.kind==kind,records.c.owner==owner).order_by(records.c.updated_at.desc()).limit(30)).mappings().all()
    return [json.loads(r['data']) for r in rows]

def update_experiment(job,allowed=('queued','running')):
    """Optimistic compare-and-swap across API and worker processes.

    Cancellation is a terminal state. A late worker must never overwrite it.
    """
    with db.begin() as conn:
        row=conn.execute(select(records.c.data).where(records.c.id==job['id'],records.c.kind=='experiment',records.c.owner==job['owner'])).first()
        if not row or json.loads(row.data)['status'] not in allowed:return False
        result=conn.execute(update(records).where(records.c.id==job['id'],records.c.data==row.data).values(
            data=json.dumps(job,ensure_ascii=False,allow_nan=False),updated_at=datetime.now(timezone.utc).isoformat()))
        return result.rowcount==1

def cancel_experiment(key,owner):
    for _ in range(10):
        job=load(key,'experiment',owner)
        if not job:return None
        if job['status'] not in ('queued','running'):return job['status']
        job['status']='cancelled'
        if update_experiment(job):return 'cancelled'
    raise ValueError('The experiment changed during cancellation. Retry cancellation.')

def recover_interrupted_experiments():
    with db.connect() as conn:
        rows=conn.execute(select(records.c.data).where(records.c.kind=='experiment')).all()
    recovered=0
    for row in rows:
        job=json.loads(row.data)
        if job['status'] in ('queued','running'):
            job.update(status='interrupted',error='The server restarted before this experiment finished. Run the same configuration again.')
            recovered+=int(update_experiment(job))
    return recovered
