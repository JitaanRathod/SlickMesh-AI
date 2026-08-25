# INTEGRATION_PLAN — Merging the Four Phases

## Data flow (who produces what, who consumes what)

```
Phase 1 (Martin)  ──► Contract A ──► Integration ──► Contract E (incident)
Phase 4a (Rudra)  ──► Contract B ──► Phase 2 (also feeds Integration directly)
Phase 2 (Jitaan)  ──► Contract C ──► Phase 3
Phase 3 (Om)      ──► Contract D ──► Integration ──► Contract E (vessels[])
Integration       ──► Contract E ──► Phase 4b dashboard
```

No phase calls another phase's code directly. Every arrow above is "write a JSON file /
respond to an HTTP GET," never a function import.

## Checkpoints

### Checkpoint 0 — Tonight, kickoff (before anyone writes code)

- Everyone reads `PRD.md` once.
- Everyone reads only their own `phaseN-*.md`.
- Phase 2 (Jitaan) starts the AIS listener running in the background immediately — this has no
  dependency on anything and only gets more valuable the longer it runs.
- Confirm `API_CONTRACTS.md` is the current agreed shape. Any objections raised now, not at
  midnight.

### Checkpoint 1 — Tomorrow morning: "own contract" DoD

Each phase produces a JSON file that validates against its own schema in `API_CONTRACTS.md`, using
its own mock input. Nobody has integrated with anybody else yet. This is the point where you
`git merge` each phase branch into `main` — `main` now contains four independently-working
modules, each still running on mocks.

### Checkpoint 2 — Tomorrow afternoon: pairwise real-data swaps

Do these one at a time, in this order (each swap is low-risk because the shape didn't change,
only the source):

1. Phase 2 swaps its mock spill centroid/timestamp for Phase 1's real Contract A output (or keeps
   the mock if Phase 1 isn't ready yet — Phase 2 does not block on this).
2. Phase 2 swaps Open-Meteo for Phase 4a's real Copernicus feed if Phase 4a is ready (optional —
   Open-Meteo is a fully valid permanent choice, not just a placeholder).
3. Phase 3 swaps its mock candidate list for Phase 2's real Contract C output.
4. Integration assembles Contract E from Phase 1 + Phase 3 (+ Phase 4a) real outputs.
5. Phase 4b swaps its dummy `incident.json` fetch for the real assembled Contract E, either as a
   static file or a live endpoint.

If any step isn't ready by its slot, **skip it and keep the mock** — the demo still works end to
end with a mix of real and mocked modules, which is the entire point of building this way.

### Checkpoint 3 — Tomorrow evening: full run-through

- Run the whole pipeline on the actual demo machine, on the actual network you'll present on.
- Take screenshots of a clean successful run and save them as a static fallback.
- Rehearse the 60-second script below with whoever is presenting.
- Confirm every teammate can explain their own module's guardrail ("what this does NOT prove") in
  one sentence.

## Fallback plan if a module isn't finished in time

| If this isn't ready... | Do this instead |
|---|---|
| Phase 1 (real SAR model) | Use a hand-picked known-good example from the SOS test set as the "detected" spill; say plainly it's a benchmark example, not a live scan |
| Phase 2 (live AIS feed) | Use the Danish AIS dev dataset or a hand-written mock candidate list matching Contract C |
| Phase 3 (attribution engine) | Ship the weighted-scoring baseline only — skip the Bayesian stretch; it was optional from the start |
| Phase 4 (live env data) | Dashboard already runs on dummy Contract E — present that, note real data as "integration in progress" |

A partially-mocked, honestly-labelled demo beats a broken live-data demo. Say what's real and
what's illustrative — judges respect that more than a crash.

## 60-second demo script

> "This dashboard shows a suspected oil spill detected from Sentinel-1 satellite imagery. The red
> polygon is the detected spill; the orange circle is the estimated source region from backtracking
> ocean currents and wind. Blue lines are AIS vessel routes near that region. The system scores each
> nearby vessel on distance, timing, heading, and track continuity relative to the backtracked
> origin — the red vessel is the highest-ranked candidate, but that score represents probable
> attribution, not legal proof. Environmental data comes from Copernicus Marine and INCOIS, and the
> whole system is built specifically for Indian waters — the Arabian Sea and Bay of Bengal."

## Final end-to-end checklist

- [ ] Contract A, B, C, D each validate against `API_CONTRACTS.md` on real (or best-available mock)
      data.
- [ ] Assembled Contract E loads in the dashboard with no manual edits.
- [ ] Map shows: spill polygon, source-region circle, ≥1 vessel track, ranked sidebar.
- [ ] At least one vessel has a real (not placeholder) reason string.
- [ ] Screenshots of a clean run saved locally as fallback.
- [ ] Script rehearsed once out loud, timed under 60 seconds.
