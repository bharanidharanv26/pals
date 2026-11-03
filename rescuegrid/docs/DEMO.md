# Seven-minute demonstration

## 0:00 — Define the objective

“RescueGrid coordinates rescue assets, ambulances, routes and receiving facilities. We measure time to appropriate treatment and report the demand still waiting.”

Show the research-mode label and the **Data & model** source information. Explain that geography is sourced, while operational capacity and casualties are simulated.

## 0:45 — National coverage

Start the national readiness exercise. Point out the 36 selectable state/UT packages and multiple incident types. Select a flood filter to show that map markers and patient counts follow the selected scope.

## 1:30 — Hospital choice

Load **Chennai · hospital saturation** with seed 42. Explain that this is a constructed scenario designed to test capacity-aware hospital choice.

Click **Optimise resources**. Inspect the chosen ambulance, rescue completion time, compatible hospital, predicted treatment queue and unallocated demand. Expand an assignment to show the reasons. Apply the plan.

## 2:30 — Follow the response

Use **Step +5m** or **Play**. Open **Incidents** and inspect rescue prerequisites, patient states and the activity log. Show that resources become available after handover and turnaround.

In **Facilities**, close new admissions at a receiving hospital. Recalculate pending demand. Explain the leg-boundary routing assumption: active travel legs finish; later legs use updated conditions.

## 3:30 — A different disaster

Load **Assam · rising water**. Explain rescue boat/crew capacity, hoist-capable air-rescue assumptions, transfer to a road-accessible location and evacuation buses to shelters. Severe weather can make water/air links unavailable, producing explicit unmet demand.

## 4:30 — Compare strategies

Open **Simulation lab**. Run the hospital-saturation scenario for 240 minutes, first with one repetition for speed. Show all three policies and the computed treatment curves.

Discuss treated counts, unmet demand, critical-patient outcomes and time averages together. A lower time average alone does not establish a better policy. The accompanying 45-run report includes scenarios where severity prioritisation increases the overall mean while improving critical-patient response.

## 5:45 — Regional support

Open **Mutual aid**, choose a receiving region, and request a desired number of advanced ambulances. Calculate placement with a minimum donor reserve of one. Mobilise the recommendation and show that the incoming units remain unavailable until the estimated transfer time.

## 6:30 — Evidence and handoff

Export the experiment JSON and event CSV. Show the stored seed, decision trace and network fingerprints. Point to `docs/EVALUATION.md`, the test coverage, architecture and stated assumptions.

Close with the research question: “Which resource or coordination change reduces the largest delay for this scenario, and what does it cost other patients or regions?”

## Before presenting

- Start the application and complete one local exercise.
- `START_RESCUEGRID.bat` runs the server in the background. Use `STOP_RESCUEGRID.bat` when finished.
- If an old browser tab is open after an update, refresh it once. A connection banner pauses playback until the saved state is reloaded.
- Keep the bundled offline map mode available.
- Fill the college name and team members on the presentation cover.
- Use the recorded results exactly as labelled; the saturation exercise is a constructed mechanism demonstration.
- Export a snapshot and keep the deck/screenshots as a presentation backup.
