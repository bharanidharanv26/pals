"""Install the locked dependencies and build the browser application."""
import subprocess
import sys
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/'.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
def run(args,cwd=ROOT):
    print('Running:', ' '.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),cwd=cwd,check=True)

if __name__=='__main__':
    if sys.version_info<(3,11):raise SystemExit('Python 3.11 or newer is required.')
    npm=shutil.which('npm.cmd' if sys.platform=='win32' else 'npm')
    if not npm:raise SystemExit('Install Node.js 22 or 24 LTS, then run setup again.')
    if not PYTHON.exists():run([sys.executable,'-m','venv',ROOT/'.venv'])
    lock=ROOT/'requirements.lock.txt'
    run([PYTHON,'-m','pip','install','-r',lock if lock.exists() else ROOT/'requirements.txt'])
    run([npm,'ci'],ROOT/'frontend')
    run([npm,'run','build'],ROOT/'frontend')
    if not (ROOT/'data'/'geography'/'states.geojson').exists():run([PYTHON,ROOT/'scripts'/'prepare_data.py'])
    print('\nSetup complete. Run START_RESCUEGRID.bat or .venv/Scripts/python.exe scripts/launch.py')
