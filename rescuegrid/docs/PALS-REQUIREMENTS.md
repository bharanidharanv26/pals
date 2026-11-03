# PALS requirement mapping

| Required topic | Implementation / evidence |
|---|---|
| Problem statement and objectives | README, architecture, presentation cover and objectives |
| Beneficiaries and research questions | Demo script; time-to-care, capacity and regional-resource questions |
| Record incident details and severity | Incident form and validated `/api/incidents` |
| Track ambulances, rescue teams, roads and hospitals | Resource, facility and map views; scenario state |
| Optimise resources, routes and hospital selection | `planner.py`, `routing.py`, `coordination.py` |
| Simulate and compare strategies | `engine.py`, `experiments.py`, Simulation lab |
| Reproducible research | Seeds, scenario snapshots, data fingerprints, event/decision traces, evaluation script |
| Explain recommendations and assumptions | Plan details, unassigned reasons, Data & model view |
| Clearly identify a research prototype | Persistent interface labels and source documentation |
| Technical architecture | `docs/ARCHITECTURE.md` |
| End-to-end workflow and use cases | Architecture workflow, demo script and browser tests |
| Detailed design and data model | Architecture algorithms, entity relations and API surface |
| User interfaces | Working application and generated screenshots |
| Infrastructure requirements | `docs/DEPLOYMENT.md`, launcher, Dockerfile, Compose, Render blueprint |
| Measured benefits | `docs/EVALUATION.md`, CSV and JSON results; no universal improvement claim |

The presentation generator reads the supplied **T2I. IT Projects Presentation.pptx** from its ZIP and builds a project-specific deck using that template. Add your college and team details before submission.
