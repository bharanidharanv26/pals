# Measured simulation results

Generated 2026-11-03T02:16:36.169229+00:00. 45 runs; 3 paired seeds per scenario; 240-minute horizon.

These are synthetic experiments on the packaged networks. They are not field estimates of Indian emergency-service performance. Time means use treated patients only; always compare unmet demand and severity-specific outcomes.

| Scenario | Policy | Mean care (min) | Treated | Unserved | Critical treated | Critical care (min) | Hospital wait (min) |
|---|---|---:|---:|---:|---:|---:|---:|
| chennai | nearest | 105.1 | 14.0 | 0.0 | 2.0 | 107.1 | 0.9 |
| chennai | priority | 117.1 | 14.0 | 0.0 | 2.0 | 59.7 | 0.3 |
| chennai | optimized | 117.0 | 14.0 | 0.0 | 2.0 | 59.7 | 0.1 |
| assam | nearest | 112.5 | 9.7 | 4.3 | 1.3 | 111.0 | 6.5 |
| assam | priority | 104.3 | 9.3 | 4.7 | 2.0 | 86.8 | 5.1 |
| assam | optimized | 99.3 | 9.0 | 5.0 | 2.0 | 86.8 | 0.0 |
| odisha | nearest | 131.3 | 13.7 | 0.3 | 2.0 | 154.8 | 1.4 |
| odisha | priority | 144.3 | 12.7 | 1.3 | 2.0 | 81.6 | 1.3 |
| odisha | optimized | 146.3 | 13.0 | 1.0 | 2.0 | 81.3 | 0.2 |
| rail | nearest | 129.4 | 11.0 | 0.0 | 2.0 | 177.8 | 1.7 |
| rail | priority | 153.9 | 10.0 | 1.0 | 2.0 | 89.1 | 1.7 |
| rail | optimized | 153.1 | 10.0 | 1.0 | 2.0 | 89.1 | 0.3 |
| capacity | nearest | 167.1 | 9.0 | 0.0 | 1.0 | 126.0 | 77.6 |
| capacity | priority | 167.1 | 9.0 | 0.0 | 1.0 | 126.0 | 77.6 |
| capacity | optimized | 100.8 | 9.0 | 0.0 | 1.0 | 70.7 | 4.8 |

## Interpretation

The local optimiser is severity-weighted and myopic: it sees reported demand and current resource commitments. A lower mean among treated patients can coincide with fewer completed treatments. The recorded critical-patient counts and unmet demand make that trade-off inspectable.

The capacity scenario deliberately places incidents next to a saturated hospital. It demonstrates the hospital-choice mechanism; it is a constructed case, not an unbiased estimate of average benefit.

Queue times, service distributions, road-class speeds and severity weights are modelling assumptions. Compare wider scenario distributions and validate with practitioners before drawing operational conclusions.

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts/evaluate.py --repetitions 3 --horizon 240
```

Raw runs, source-network hashes and the engine hash are in `benchmark-results.json`.
