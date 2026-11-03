# Local and hosted deployment

## Windows demonstration

The installed project launches with `START_RESCUEGRID.bat`. It calls the project's Python interpreter directly, starts a detached server, waits for verified application health, and opens the browser. PowerShell activation policy does not affect startup, and closing the launcher does not stop the server.

Use `STOP_RESCUEGRID.bat` to stop it. The stop command checks the application's process ID and instance identifier against the local launcher record before terminating that process tree. It does not terminate unrelated programs occupying the same port.

```powershell
.\.venv\Scripts\python.exe scripts/launch.py --background
.\.venv\Scripts\python.exe scripts/launch.py --status
.\.venv\Scripts\python.exe scripts/launch.py --stop --no-browser
```

Background logs are appended to `runtime/server-PORT.log`, and process metadata is stored in `runtime/server-PORT.json`. Omit `--background` to run in the foreground during development.

To share on your local network, stop an existing local-only instance first, then run:

```powershell
.\.venv\Scripts\python.exe scripts/launch.py --host 0.0.0.0 --background
```

Open `http://YOUR-LAPTOP-IP:8000` from the other device. Windows may request permission for local-network access. Phone testing should include the software keyboard, scrolling, landscape orientation and language changes; browser emulation alone does not establish touch behaviour.

## Configuration

Copy `.env.example` to `.env` and set the values you need. `scripts/launch.py` reads `DATABASE_URL`, `SACHET_FEED_URL`, and `PORT`. Existing environment variables take precedence. When invoking Uvicorn directly, set those environment variables in your shell instead.

Default persistence is `runtime/rescuegrid.db`. Each browser retains its workspace ID in local storage. Export snapshots and experiments using the application. Back up the SQLite file while the server is stopped.

The prototype uses in-process locks for interactive updates and must run **one API worker**. It starts one additional spawned process for controlled experiments and admits a bounded queue. On startup, unfinished experiments are labelled **interrupted**; their configurations remain available for rerunning. Cancelled jobs cannot be revived by a late worker write. Saved workspaces and completed results are retained.

The browser pauses playback if it loses the connection. Reconnection reads the saved authoritative state before allowing another step. An expected-revision check prevents an obsolete playback request from advancing a changed workspace. Automatic retries apply to reads, not to state-changing commands.

## Docker / Compose

```text
docker compose up --build
```

Open http://localhost:8000. Compose mounts a named volume at `/app/runtime`. The image bundles the frontend, map worker, fonts and geographic packages. The container runs as a non-root user and installs the native runtime libraries required by the scientific packages. Containers keep the API in the foreground; `--background` is for the local desktop launcher.

Docker was not installed in the development environment, so this container definition has not been executed there. The equivalent native Python/Node production build and HTTP application were exercised by browser tests.

## Hosted website

The included `render.yaml` describes a Docker web service with `/api/health` as its health check. Deployment requires a repository accessible to your hosting account; no remote repository or hosted site has been created automatically.

1. Upload the project to your own repository, excluding `.venv`, `node_modules`, `runtime`, and `.env`.
2. Create a Docker web service using the project root as the build context, or use the blueprint.
3. Configure the service to use its assigned port; the launcher reads `PORT`.
4. For retained workspaces, set `DATABASE_URL` to a PostgreSQL database URL, or provision a persistent writable `/app/runtime` directory.
5. Verify `/api/health`, then complete an incident-to-dispatch flow and one simulation experiment.

Without persistent storage, local SQLite data disappears when an ephemeral hosted filesystem is replaced. The application remains a session-isolated demonstration; it does not implement agency user accounts.

Allow memory for both the API and a simulation worker. Small free tiers may sleep or impose CPU/memory limits. The local build is the reliable presentation path; actual hosting tiers and persistence settings must be selected in your account.

## Rebuild after source changes

In `frontend`, run `npm run build`, then restart the server. The server serves the generated assets from `frontend/dist`.

After changing an OSM package, restart the server and load a fresh exercise, because graph node IDs and paths belong to a specific data version. Keep old exports with their source hashes for research provenance.
