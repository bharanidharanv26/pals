# Verification record

Development environment: Windows, Python 3.11.9, Node.js 24.13.0.

| Check | Result |
|---|---|
| Backend engine/API suite | 38 passing tests |
| Frontend TypeScript and Vite production build | Passed |
| Chromium end-to-end suite | 10 passing tests |
| Offline national map | Passed with external browser requests blocked |
| Chennai regional road rendering | Passed, including source readiness |
| Anonymous workspace isolation and stale-plan rejection | Passed |
| Capacity, capability, resource exclusivity and disaster workflows | Passed |
| Hindi/Tamil navigation and 390px viewport | Passed in browser emulation |
| Persistent local launcher | Passed: launch command exits, repeated start reuses the same server |
| Continuous Play beyond the former 30-second failure | Passed on a separately launched background server |
| Actual server stop/restart | Passed: same workspace, simulation clock and mission data restored |
| Lost response after a committed step | Passed: playback pauses; reconnect reads the saved result without replaying the command |
| Stale region fetch and map scroll behaviour | Passed: late geometry cannot replace All India; page scrolling does not zoom the map |
| Cancelled/interrupted experiment recovery | Passed: terminal status is preserved against late worker updates |
| Repeated simulation evidence | 45 paired runs generated in CSV/JSON/Markdown |
| Public USGS connector | Successfully fetched public observations during verification |
| npm dependency audit | No reported vulnerabilities after MapLibre update |
| PALS deck generation | 20 slides; generated PPTX reopened and titles verified |

The Python suite emits a Starlette notice about the future HTTP test-client dependency. All assertions pass.

The reliability fix addresses the reported **Failed to fetch** error: previous foreground launches were terminated by the command runner after 30 seconds. The default Windows launcher now uses a detached process, with verified startup, start/stop controls and a persistent log. Browser tests use an isolated port/database and an actual process lifecycle test, rather than relying only on a server held open by the test runner.

Actual phone hardware, Docker execution, managed PostgreSQL deployment and a publicly hosted URL were not available for verification in this environment. Those are distinct from the tested native application and packaged deployment definitions.

The measured evaluation includes policy trade-offs. A passing software test does not establish real-world operational effectiveness. Read the model assumptions and raw outcomes with the evaluation report.
