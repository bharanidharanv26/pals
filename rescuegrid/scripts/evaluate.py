"""Run paired experiments and write a measured report; no network calls."""
import argparse,csv,hashlib,io,json,statistics,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.scenarios import create_world
from backend.engine import advance,metrics

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--horizon',type=int,default=240)
    parser.add_argument('--presets',nargs='+',default=['chennai','assam','odisha','rail','capacity'])
    args=parser.parse_args();out=ROOT/'docs';out.mkdir(exist_ok=True)
    records=[];started=time.perf_counter();versions={}
    for preset in args.presets:
        for seed in range(42,42+args.repetitions):
            for policy in ['nearest','priority','optimized']:
                begin=time.perf_counter();s=create_world(preset,seed)
                advance(s,args.horizon,policy)
                m=metrics(s);versions=s['data_versions']
                record=dict(scenario=preset,seed=seed,policy=policy,mean_care_minutes=m['time_to_care']['mean'],p90_care_minutes=m['time_to_care']['p90'],
                    treated=m['treated'],unserved=m['unserved'],critical_treated=m['by_severity']['critical']['treated'],critical_total=m['by_severity']['critical']['total'],
                    critical_care_minutes=m['by_severity']['critical']['time_to_care']['mean'],
                    mean_response_minutes=m['response']['mean'],hospital_wait_minutes=m['hospital_wait']['mean'],evacuated=m['evacuated'],
                    evacuation_demand=m['evacuation_demand'],runtime_seconds=round(time.perf_counter()-begin,3))
                records.append(record)
                print(f'{preset:10} seed={seed} {policy:9} treated={m["treated"]:2} unserved={m["unserved"]:2} care={m["time_to_care"]["mean"]} min',flush=True)
    report=dict(created_at=datetime.now(timezone.utc).isoformat(),horizon=args.horizon,repetitions=args.repetitions,seed_start=42,data_versions=versions,
        engine_hash=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'backend').glob('*.py')))).hexdigest(),
        duration_seconds=round(time.perf_counter()-started,2),records=records)
    (out/'benchmark-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (out/'benchmark-results.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    lines=['# Measured simulation results','',f"Generated {report['created_at']}. {len(records)} runs; {args.repetitions} paired seeds per scenario; {args.horizon}-minute horizon.",'',
        'These are synthetic experiments on the packaged networks. They are not field estimates of Indian emergency-service performance. Time means use treated patients only; always compare unmet demand and severity-specific outcomes.','',
        '| Scenario | Policy | Mean care (min) | Treated | Unserved | Critical treated | Critical care (min) | Hospital wait (min) |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    def mean(rows,key):
        vals=[r[key] for r in rows if r[key] is not None]
        return f'{statistics.mean(vals):.1f}' if vals else '—'
    for preset in args.presets:
        for policy in ['nearest','priority','optimized']:
            rows=[r for r in records if r['scenario']==preset and r['policy']==policy]
            lines.append(f"| {preset} | {policy} | {mean(rows,'mean_care_minutes')} | {mean(rows,'treated')} | {mean(rows,'unserved')} | {mean(rows,'critical_treated')} | {mean(rows,'critical_care_minutes')} | {mean(rows,'hospital_wait_minutes')} |")
    lines += ['', '## Interpretation','',
        'The local optimiser is severity-weighted and myopic: it sees reported demand and current resource commitments. A lower mean among treated patients can coincide with fewer completed treatments. The recorded critical-patient counts and unmet demand make that trade-off inspectable.',
        '', 'The capacity scenario deliberately places incidents next to a saturated hospital. It demonstrates the hospital-choice mechanism; it is a constructed case, not an unbiased estimate of average benefit.',
        '', 'Queue times, service distributions, road-class speeds and severity weights are modelling assumptions. Compare wider scenario distributions and validate with practitioners before drawing operational conclusions.',
        '', '## Reproduce','', f'```powershell\n.\\.venv\\Scripts\\python.exe scripts/evaluate.py --repetitions {args.repetitions} --horizon {args.horizon}\n```',
        '', 'Raw runs, source-network hashes and the engine hash are in `benchmark-results.json`.']
    (out/'EVALUATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Wrote {len(records)} runs to docs/ in {report["duration_seconds"]:.1f} seconds')

if __name__=='__main__':main()
