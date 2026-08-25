# GUIDELINES — How We Work

## The golden rule: contract-first, mock-first

Nobody waits on anybody tonight. Every phase doc defines:

1. **The exact JSON it must produce** (its output contract).
2. **A ready-to-use mock/dummy input** that stands in for whatever an upstream module would
   otherwise supply.

Build against the mock. Validate your own output against your own contract. Integration is a
later, scheduled step (`INTEGRATION_PLAN.md`) where mocks get swapped for real data — it is
**not** something that happens accidentally at 11pm because two people finally opened a call.

## Repo / folder structure

Each phase gets its own top-level folder with its own dependency file. No phase imports code from
another phase's folder — the only thing that crosses a folder boundary is a JSON file (or an HTTP
call returning one).

```
phase1-satellite/   requirements.txt   (own venv)
phase2-ais-gis/      requirements.txt   (own venv)
phase3-attribution/  requirements.txt   (own venv)
phase4-dashboard/    package.json or none (static HTML/JS)
```

If two phases genuinely need the same helper (e.g. haversine distance), copy the ~10 lines rather
than introduce a shared-library dependency tonight. Optimize for zero coordination overhead, not
DRY.

## Branching

- `main` stays deployable/demoable at all times after the first integration checkpoint.
- One branch per phase: `phase1-satellite`, `phase2-ais-gis`, `phase3-attribution`,
  `phase4-dashboard`.
- Merge into `main` only at a scheduled integration checkpoint, and only after your output has
  been validated against its schema.

## Coding conventions

- **Python** (Phases 1–3): type hints on function signatures, docstring on any function that
  isn't self-evident, `pydantic` models mirroring the JSON contracts (catches schema drift at
  import time instead of at demo time).
- **JS/HTML** (Phase 4): no build step required — plain HTML/CSS/JS is fine and faster to demo;
  keep `app.js` reading from one `fetch()` call so swapping mock→real is a one-line change.
- Every output-producing script should have a `--mock` flag (or equivalent) that writes the
  sample JSON from its own phase doc, so anyone can `diff` their real output's *shape* against a
  known-good example at any time.

## Definition of Done (generic — each phase doc has a specific version)

A phase is "done" for integration purposes when:

- [ ] Running it produces a JSON file that validates against its own contract in
      `API_CONTRACTS.md`.
- [ ] It runs end-to-end against the mock input with zero manual steps.
- [ ] At least one qualitative sanity check has been eyeballed (a plotted mask, a plotted
      trajectory, a printed ranked list — whatever "looks right" means for that phase).
- [ ] The "what not to claim" guardrail for that phase has been read by whoever demos it.

## Contract change protocol

`API_CONTRACTS.md` is the single source of truth, but every phase doc embeds the schema it needs
inline so nobody has to jump files mid-build. If you need to change a field:

1. Post it to the team channel before changing code — one sentence: "adding `wind_direction_deg`
   to the env contract, defaults to null if missing."
2. Update `API_CONTRACTS.md`.
3. Update every phase doc that embeds that schema.
4. Only then change your code.

This is the one place independence stops — schema drift is the failure mode that turns four
working modules into a broken demo at midnight.

## Guardrails (repeated here on purpose — internalize these)

- SAR = surface-roughness anomaly, not confirmed oil.
- Benchmark score ≠ real-world accuracy.
- AIS proximity = evidence, not legal proof.
- Origin corridor = uncertainty band, not a pinpoint.
- Attribution score = probabilistic triage, never "the responsible vessel."

## Demo-day checklist

- [ ] End-to-end run rehearsed on the actual demo machine/network (not just a laptop that "should
      be fine").
- [ ] Screenshots of a good run saved as a fallback if live data/network fails.
- [ ] 60-second script rehearsed by whoever is presenting (see `INTEGRATION_PLAN.md`).
- [ ] Each teammate can answer "what does your module do and why should I trust it?" in under 30
      seconds.
