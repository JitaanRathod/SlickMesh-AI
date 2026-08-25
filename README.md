# SIH26143 — Satellite Oil-Spill Detection & AIS Vessel Attribution

**Problem Statement:** SIH26143 — detect marine oil spills from satellite imagery, reason about
drift using ocean/weather data, and correlate the inferred origin with AIS vessel traffic to
shortlist the probable source vessel.

**Hard deadline:** internal hackathon round, 26 Aug 2026. Everything in this repo is scoped to
what four people can build in one overnight sprint — not a production system.

## Team & Ownership

| Phase | Owner | Module | Doc |
|---|---|---|---|
| 1 | Martin | Satellite SAR detection (Sentinel-1 → U-Net → spill mask/polygon) | [`docs/phase1-satellite-detection.md`](docs/phase1-satellite-detection.md) |
| 2 | Jitaan | AIS ingestion, trajectory reconstruction, spatial-temporal matching, drift backtracking | [`docs/phase2-ais-gis-backtracking.md`](docs/phase2-ais-gis-backtracking.md) |
| 3 | Om | Attribution engine — evidence fusion, weighted scoring, ranked explainable output | [`docs/phase3-attribution-engine.md`](docs/phase3-attribution-engine.md) |
| 4 | Rudra (Person 4) | Environmental data sourcing + dashboard/demo shell | [`docs/phase4-environmental-dashboard.md`](docs/phase4-environmental-dashboard.md) |

## Why this structure

The four phases are cut along the **existing evidence-ownership boundaries** the team already
researched independently, and each phase doc is written to be **fully buildable in isolation**:
every phase defines its own mock input, so no one is blocked waiting on anyone else's code
tonight. The only thing that must never drift out of sync is the JSON shape each phase produces —
that's why it's pulled out into one canonical file (`docs/API_CONTRACTS.md`) that every phase doc
also embeds inline, so an agent working phase-by-phase never has to open a second file to know
what to build.

```
detect (Martin) ──► spill polygon + centroid + timestamp ─┐
                                                             ├──► attribution (Om) ──► dashboard (Rudra)
backtrack (Jitaan) ──► candidate vessels + origin corridor ─┘
                          ▲
env data (Rudra) ─────────┘ (wind/current feed — Jitaan can also self-serve this via Open-Meteo)
```

## Repo layout

```
SIH26143-project/
├── README.md                                   ← you are here
└── docs/
    ├── PRD.md                                  ← what we're building & why, MVP vs stretch
    ├── GUIDELINES.md                           ← how we work: contract-first, mock-first, DoD
    ├── SKILLS.md                               ← stack/libraries/accounts needed per phase
    ├── API_CONTRACTS.md                        ← canonical JSON schemas (source of truth)
    ├── INTEGRATION_PLAN.md                     ← merge timeline + fallback plan + demo script
    ├── phase1-satellite-detection.md           ← Martin, self-contained
    ├── phase2-ais-gis-backtracking.md          ← Jitaan, self-contained
    ├── phase3-attribution-engine.md            ← Om, self-contained
    └── phase4-environmental-dashboard.md       ← Rudra, self-contained
```

## How to use this with Antigravity

Each `phaseN-*.md` is written to be dropped in as the **entire context an agent needs** to build
that module — goal, mock input, exact output contract, step-by-step plan, definition of done, and
guardrails, with nothing that requires reading another phase file. Practically:

1. Open four parallel Antigravity workspaces/tasks, one per phase file, one per teammate.
2. Each agent builds against the **mock input** given in its own phase doc and validates its
   output against the **JSON schema** embedded in that same doc — never against another
   teammate's actual code.
3. `docs/API_CONTRACTS.md` is edited by nobody solo — a schema change there must be echoed into
   every phase doc that references it (see `GUIDELINES.md` → "Contract change protocol").
4. At the integration checkpoints in `INTEGRATION_PLAN.md`, swap each module's mock
   input/output for the real thing from its upstream/downstream neighbour. Nothing about a
   module's internals should need to change — only which JSON it's pointed at.

Read `docs/PRD.md` first if you want the full picture; read only your own `phaseN-*.md` if you
just want to start building.
