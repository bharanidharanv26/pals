"""Run RescueGrid in the foreground or as a persistent local background service."""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'
sys.path.insert(0,str(ROOT))

def server_health(port):
    """Identify this application, rather than trusting any listener on the port."""
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{port}/api/health',timeout=2) as response:
            data=json.load(response)
            return data if data.get('service')=='rescuegrid-india' else None
    except (OSError,ValueError):
        return None

def port_in_use(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1):return True
    except OSError:return False

def stop_server(port):
    path=RUNTIME/f'server-{port}.json'
    health=server_health(port)
    if not health:
        print(f'RescueGrid is not responding on port {port}. No process was stopped.')
        return
    if not path.exists():
        raise SystemExit('This server was started in another terminal. Stop it there with Ctrl+C.')
    record=json.loads(path.read_text(encoding='utf-8'))
    if record.get('instance_id')!=health.get('instance_id') or record.get('pid')!=health.get('pid'):
        raise SystemExit('The running server does not match this launcher record. No process was stopped.')
    pid=health['pid']
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],check=True)
    else:
        # Background servers get their own session/process group, including the job worker.
        os.killpg(record['launcher_pid'],signal.SIGTERM)
    deadline=time.monotonic()+10
    while port_in_use(port) and time.monotonic()<deadline:time.sleep(.2)
    if port_in_use(port):raise SystemExit('The server has not stopped yet. Check the server log.')
    path.unlink(missing_ok=True)
    print(f'RescueGrid stopped. Saved workspaces remain in the database.')

def background_server(args,url):
    RUNTIME.mkdir(exist_ok=True)
    log_path=RUNTIME/f'server-{args.port}.log'
    command=[sys.executable,str(Path(__file__).resolve()),'--host',args.host,'--port',str(args.port),'--no-browser']
    kwargs=dict(cwd=str(ROOT),stdin=subprocess.DEVNULL,close_fds=True)
    if os.name=='nt':
        kwargs['creationflags']=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP
    else:kwargs['start_new_session']=True
    with log_path.open('ab',buffering=0) as log:
        log.write(f'\n--- RescueGrid start {time.strftime("%Y-%m-%d %H:%M:%S")} ---\n'.encode())
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,**kwargs)
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        health=server_health(args.port)
        if health:
            record=dict(pid=health['pid'],launcher_pid=process.pid,instance_id=health['instance_id'],port=args.port,url=url,log=str(log_path))
            (RUNTIME/f'server-{args.port}.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
            print(f'RescueGrid is running in the background: {url}\nServer PID: {health["pid"]}\nLog: {log_path}\nUse STOP_RESCUEGRID.bat to stop it.')
            if not args.no_browser:webbrowser.open(url)
            return
        if process.poll() is not None:
            raise SystemExit(f'The server exited during startup. Read {log_path} for the error.')
        time.sleep(.25)
    raise SystemExit(f'Startup was not confirmed. Check {log_path} before starting another instance.')

def main():
    env_file=ROOT/'.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:continue
            key,value=line.split('=',1)
            if key.strip() in ('DATABASE_URL','SACHET_FEED_URL','PORT'):
                os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))
    parser=argparse.ArgumentParser(description='Start RescueGrid India')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8000')))
    parser.add_argument('--no-browser',action='store_true')
    controls=parser.add_mutually_exclusive_group()
    controls.add_argument('--background',action='store_true',help='Start a detached server that survives this terminal')
    controls.add_argument('--status',action='store_true',help='Check the running local service')
    controls.add_argument('--stop',action='store_true',help='Stop the background service started by this launcher')
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('Port must be between 1 and 65535')
    if args.stop:
        stop_server(args.port)
        return
    health=server_health(args.port)
    if args.status:
        print(json.dumps(health or {'status':'stopped','port':args.port}))
        return
    url=f'http://127.0.0.1:{args.port}'
    if health:
        print(f'RescueGrid is already running: {url} (PID {health["pid"]})')
        if not args.no_browser:webbrowser.open(url)
        return
    if port_in_use(args.port):
        raise SystemExit(f'Port {args.port} is occupied by an unrecognised service. Choose another --port; no process was stopped.')
    if not (ROOT/'frontend'/'dist'/'index.html').exists():
        raise SystemExit('Frontend build missing. Run SETUP_RESCUEGRID.bat first.')
    if args.background:
        background_server(args,url)
        return
    if not args.no_browser:
        def open_when_ready():
            for _ in range(60):
                if server_health(args.port):webbrowser.open(url);return
                time.sleep(.5)
        threading.Thread(target=open_when_ready,daemon=True).start()
    print(f'RescueGrid India: {url}\nAPI documentation: {url}/docs\nPress Ctrl+C to stop.')
    import uvicorn
    uvicorn.run('backend.app:app',host=args.host,port=args.port,workers=1)

if __name__=='__main__':main()
