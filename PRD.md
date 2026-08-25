# PRD — SIH26143 Oil-Spill Detection & Vessel Attribution

## 1. Problem statement

SIH26143 asks for an automated pipeline that (a) detects and characterises marine oil spills from
satellite imagery, (b) uses oceanographic and meteorological data to reason about where the slick
came from and where it's heading, and (c) reconstructs vessel traffic around the inferred origin
window to help identify the vessel responsible.

We are **not** building a legally admissible forensic tool. We are building a **candidate
detection and evidence-ranking assistant** — a system that narrows a huge search space (which of
thousands of vessels could plausibly be responsible) down to a short, explainable, ranked list.

## 2. Objective

Ship a working, demoable, end-to-end pipeline by the internal hackathon round:

`Sentinel-1 SAR image → spill mask/polygon → drift-backtracked origin corridor → AIS candidate
vessels → weighted evidence score per vessel → ranked list on a live map dashboard`

## 3. Audience

- **Immediate:** hackathon judges — needs to be visually convincing, explainable in one minute,
  and honest about its limitations (judges will push on both).
- **Notional real-world user:** coastal/maritime pollution-control authorities (e.g. INCOIS,
  Coast Guard) doing first-pass triage after a spill is reported — not the final word.

## 4. System architecture

```
                    ┌─────────────────────────┐
                    │  PHASE 1 — Martin        │
                    │  Sentinel-1 SAR → U-Net  │
                    │  → spill mask/polygon    │
                    └────────────┬─────────────┘
                                 │ spill polygon, centroid,
                                 │ timestamp, confidence
                                 ▼
┌──────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│ PHASE 4a — Rudra  │──►│  PHASE 2 — Jitaan        │──►│  PHASE 3 — Om            │
│ Env data (wind/   │   │  AIS ingestion → traject │   │  Evidence fusion →       │
│ current/waves)    │   │  -ory recon → candidate  │   │  weighted score →        │
└──────────────────┘   │  vessels + origin corridor│   │  ranked, explainable list│
                        └─────────────────────────┘   └────────────┬────────────┘
                                                                     │ ranked vessels +
                                                                     │ reason strings
                                                                     ▼
                                                        ┌─────────────────────────┐
                                                        │  PHASE 4b — Rudra        │
                                                        │  Leaflet dashboard       │
                                                        │  (map + sidebar + rank)  │
                                                        └─────────────────────────┘
```

## 5. Module ownership & MVP scope

| Phase | Owner | Must-have (MVP) | Stretch (only if time remains) |
|---|---|---|---|
| 1 — Satellite | Martin | U-Net trained on SOS dataset producing a binary mask + polygon + confidence on held-out test images | MobileNetV2-DeepLabV3+ comparison; wind-based quality flag |
| 2 — AIS/GIS | Jitaan | Clean→trajectory pipeline on one real/mock spill centroid+time; scored candidate vessel list; single-vector reverse-drift origin corridor | Bidirectional forward+backward drift convergence; time-varying wind/current fields |
| 3 — Attribution | Om | Weighted linear scoring over Phase 2's evidence fields → 0–100 confidence + one-line reason string, correctly sorted | Bayesian refinement layer on top of the same features |
| 4 — Env + Dashboard | Rudra | Leaflet map with spill polygon, source-region circle, vessel tracks, ranked sidebar, driven by dummy JSON matching the final contract | Live environmental-arrow overlay (wind/current vectors); "why this vessel" popup breakdown |

## 6. Non-goals / explicitly out of scope

- Real-time production deployment, authentication, multi-tenant infrastructure.
- Full Lagrangian particle-cloud drift simulation (GNOME-style) with diffusion and oil weathering
  — described as prior art, not implemented.
- Any claim of legal/forensic proof of responsibility.
- Training a model that consumes proprietary/restricted mission AIS data (Sentinel-1C/1D onboard
  AIS is access-restricted — do not build around it).

## 7. Guardrails — what we will never claim

These recur across every module's own research and must hold in the demo script, the report, and
any judge Q&A:

- SAR detects a **surface-roughness anomaly**, not petroleum chemistry. A slick candidate is
  "possible oil," never confirmed oil.
- A benchmark IoU/Dice score on the SOS dataset is **not** a claim about real-world accuracy —
  say so explicitly if asked.
- AIS proximity to an inferred origin is **evidence**, not proof of legal responsibility.
- A backtracked "origin corridor" is an **uncertainty band**, never a single pinpointed source
  location.
- Attribution scores are **probabilistic triage**, always phrased as "probable" / "candidate," never
  "the vessel responsible."

## 8. Success criteria for the demo

1. A single button/page load shows: spill polygon → source-region circle → vessel tracks → ranked
   sidebar, all on one map, without manual data wiring during the demo.
2. At least one flagged vessel has a plain-English reason string a non-technical judge can read
   in under 5 seconds.
3. Team can answer "how is this different from CleanSeaNet/Cerulean?" with the novelty statement
   in §9 without hesitation.
4. Every module can be demoed to *some* degree even if another module didn't finish — because
   each was built against a mock contract, not a live dependency.

## 9. Novelty statement (for the pitch)

> "We propose a low-cost, India-focused, explainable dashboard that combines Sentinel-1 oil-spill
> segmentation, AIS vessel tracks, Indian Ocean environmental data, and visual drift backtracking
> to rank probable source vessels with a transparent, per-feature score breakdown."

We are **not** claiming to be first to combine satellite + AIS (CleanSeaNet and Cerulean already
do that operationally). The defensible gap is: **open**, **India/Arabian-Sea/Bay-of-Bengal-tuned**
(via INCOIS), and **explainable** (visible per-feature scoring, not a black box).

## 10. Timeline (generic — adapt clock to actual start time)

| Window | Focus |
|---|---|
| Tonight | Each phase builds independently against its mock contract. Phase 2 starts an AIS listener running in the background immediately (data accumulates over time — the earlier it starts, the better). |
| Tomorrow morning | Each phase reaches "produces valid output against its own contract" — Definition of Done in each phase doc. First integration checkpoint (see `INTEGRATION_PLAN.md`). |
| Tomorrow afternoon | Real outputs swapped in place of mocks, one pairwise link at a time. |
| Tomorrow evening | End-to-end run-through on the actual demo machine/projector; screenshots taken as a fallback if live demo risk is high; 60-second script rehearsed. |

## 11. Top risks (consolidated)

| Risk | Phase(s) affected | Mitigation |
|---|---|---|
| Look-alikes cause false positives in SAR | 1 | Wind-based quality flag; honest reporting, not over-tuned thresholds |
| Domain shift from benchmark to real scenes | 1 | Present as prototype; qualitative test set with hard examples |
| AIS coverage gaps mid-ocean | 2 | Danish AIS dataset for offline pipeline dev; GFW as cross-check |
| Attribution weights are hand-set, not learned | 3 | State this openly in the pitch — it's honest and still defensible for a prototype |
| Integration left too late | 1–4 | Mock-first development (this whole repo); integration checkpoints scheduled, not improvised |
| Overclaiming certainty to judges | 1, 2, 3 | Guardrail language in §7, baked into every phase doc's output (reason strings, confidence framing) |
