# RescueGrid Chennai

A working decision-support and simulation prototype for **PALS ITPRBLM–B: Intelligent Emergency Rescue and Medical Response Optimisation**.

The application coordinates rescue, evacuation, ambulance transport and appropriate treatment across **eight Chennai zones**. It includes a city command map on the real Chennai road network, capacity-aware recommendations, controlled strategy comparisons and timed zone assistance.

## Start on this computer

Double-click **`START_RESCUEGRID.bat`**. It starts the API and built frontend **in the background**, waits for a successful health check, then opens **http://127.0.0.1:8000**. The launcher window can close without stopping the application. Starting it again reuses the existing server.

Alternatively, from `D:\pals\rescuegrid`:

```powershell
.\.venv\Scripts\python.exe scripts/launch.py --background
```

Your Command Prompt activation command also works:

```bat
d:\pals\rescuegrid\.venv\Scripts\activate.bat
python scripts/launch.py --background
```

Double-click **`STOP_RESCUEGRID.bat`** to stop the background server. Workspaces and completed experiments are stored in `runtime/rescuegrid.db`. The browser keeps an anonymous workspace identifier; a different browser starts an isolated workspace.

```powershell
.\.venv\Scripts\python.exe scripts/launch.py --status
.\.venv\Scripts\python.exe scripts/launch.py --stop --no-browser
```

The server log is `runtime/server-8000.log`. For foreground development, omit `--background`, keep that terminal open, and stop with **Ctrl+C**.

If the server is stopped or a request loses its connection, playback pauses and the interface shows a connection banner. Start the server again; the application reloads the saved workspace automatically, or you can click **Reconnect**. It does not replay a possibly committed action or resume playback without your input. After an application update, refresh an already-open browser tab once to load the new build.

## First demonstration

1. Explore **Overview** and select a Chennai zone or a disaster filter.
2. Choose **Load exercise → Chennai · hospital saturation**.
3. Click **Optimise resources**. Inspect rescue assignments, receiving hospitals, treatment predictions and queued demand.
4. **Apply dispatch plan**, then use **Play** or **Step +5m**.
5. Inspect **Incidents**, **Resources**, and **Facilities** as the response progresses.
6. Run a **Simulation lab** comparison using the same scenario and a 240-minute horizon.
7. Open **Mutual aid** to calculate resource placement while preserving donor reserves.

The simulation clock begins at 00:00 and represents elapsed exercise time. The current state is simulated; public observations have a separate source panel.

## Implemented coverage

- 8 Chennai zone packages, 136 simulated assets and 32 simulated facilities in the default configuration.
- 12 response playbooks across 10 disaster families: road, rail, flood, cyclone, earthquake/collapse, landslide/avalanche, fire/explosion, chemical incidents, tsunami/coastal flooding, heatwave, medical-demand surge, and drought-related emergencies.
- A real OpenStreetMap road package for **Chennai**, shared by all eight zones. Zone boundaries are operational groupings, not administrative boundaries.
- Rescue boats, hoist-capable helicopter assumptions, dedicated specialist crews, ambulances and evacuation buses.
- Hospital capabilities, treatment-bay schedules, evacuation capacity, resource turnaround and scenario disruptions.
- CP-SAT rescue assignment, patient/hospital scheduling and cross-region pre-positioning.
- Three comparable dispatch policies, seeded experiments, recorded event replay, JSON and CSV exports.
- English, Hindi and Tamil navigation, controls, forms, resource and disaster labels. Source documents, generated analytical explanations and scenario descriptions currently retain their English wording.
- Public USGS observations around India; a configurable NDMA SACHET CAP/RSS adapter; CAP/XML import with status preserved.

## New installation

Requirements: Python **3.11+**, Node.js **22 or 24 LTS**, and approximately 8 GB RAM for the local demo plus a browser.

Run `SETUP_RESCUEGRID.bat`, or:

```powershell
python scripts/setup.py
```

Setup creates `.venv`, installs `requirements.lock.txt`, runs `npm ci`, and builds the frontend. Geographic packages are included. Internet access is needed to install dependencies or refresh external data; the packaged operational demo and fonts work locally without it.

## Development

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Frontend, in `frontend`:

```powershell
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` and `/geography` to the backend. API documentation is at http://127.0.0.1:8000/docs.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

In `frontend`:

```powershell
npm run build
npx playwright install chromium
npx playwright test
```

Browser checks exercise offline map loading, incident creation, actual dispatch, simulation advancement, road-package rendering, facility changes, background experiments, recorded replay, mutual aid and three-language responsive navigation. Reliability checks run continuous **Play**, keep a background server alive beyond the former 30-second failure, stop/restart the actual server, and verify recovery without duplicate actions. They also exercise stale map requests and page scrolling over the map.

Tests use separate databases. The standard browser test server runs on port **8010**, and the lifecycle test uses its own free port. Your normal port-8000 workspace is preserved. Desktop and 390px browser screenshots are generated under `frontend/test-results/`. Physical-device touch behaviour still requires a phone check.

Measured research runs:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate.py --repetitions 3 --horizon 240
```

Read `docs/EVALUATION.md` alongside the raw CSV/JSON. No improvement percentage is hard-coded into the interface.

## Geographic and public-data setup

### Refresh the Chennai road package

Stop the app, import a bounded Chennai package, restart, and reset the exercise:

```powershell
.\.venv\Scripts\python.exe scripts/import_osm.py --region TN --radius 12000
.\.venv\Scripts\python.exe scripts/compact_networks.py
```

The imported Chennai graph is used by all eight zones. Imported OSM graphs use assumed road-class speeds, explicit directionality and connected road components. Turn restrictions, road surface suitability and live traffic are not modelled.

Water/air rescue and zone transfers use explicit simulated connections rather than a turn-by-turn inter-city graph.

### Public observations and alerts

**Data & model** offers USGS magnitude-2.5+ observations from the last week in the 6–38° N, 68–98° E window, which includes neighbouring countries. These observations never generate patients automatically.

To connect SACHET, copy `.env.example` to `.env` and set `SACHET_FEED_URL` to its current published HTTPS CAP/RSS URL. The launcher loads this file. The adapter follows ETag/304 caching and reports unavailable or stale data explicitly. Its default state is **not configured**. See the linked official integration guide on the source page.

`data/examples/exercise-alert.xml` is a clearly marked CAP exercise file for testing the importer.

## Deployment

See `docs/DEPLOYMENT.md`. The repository includes a multi-stage Dockerfile, Compose volume configuration, and a Render blueprint. The backend serves the built frontend, so the hosted site needs one application origin. Set `DATABASE_URL` for PostgreSQL persistence, or provide a persistent `/app/runtime` volume for SQLite.

## Model boundaries

Operational data is synthetic. The app demonstrates allocation and simulation, with scenario severity supplied by the operator. It does not connect to 112/108 dispatch, live ambulance GPS, or live hospital bed systems.

Optimisation is staged, rolling and bounded. CP-SAT optimality refers to the current candidate model. Existing trips finish their current leg; subsequent legs use updated routes and facility conditions. Medical and non-medical rescue batches have separate readiness times. Approximate regional links include mobilisation time and donor reserves.

The prototype has anonymous demonstration workspaces, not operational agency identity and access management. Its resource models and service-time assumptions require field validation before operational use.

## Project layout

```text
backend/       API, domain catalogue, routing, planning, simulation, storage
frontend/      React application, local map worker, translations, browser tests
data/          Attributed geography, road packages, example CAP document
scripts/       Setup, launch, data import, evaluation, presentation generation
tests/         Engine and API invariants
docs/          Architecture, assumptions, evaluation, demo and PALS material
```

Source attribution and data licenses are documented in `docs/DATA-SOURCES.md` and exposed in the application.
