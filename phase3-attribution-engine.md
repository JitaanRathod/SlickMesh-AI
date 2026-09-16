# Phase 3 — Attribution Engine (Evidence Fusion & Ranking)

**Owner:** Om
**Independence:** This phase needs only a list of candidate vessels with raw evidence attached —
use the mock in §2 and never wait on Phase 2's actual AIS pipeline to be running.

## 1. Mission

Take each candidate vessel's raw evidence (distance, timing, heading, speed, type, continuity,
environmental consistency) and turn it into one 0–100 confidence score plus a short, honest,
human-readable reason string — sorted, ready for the dashboard.

## 2. Mock input (build against this — matches Phase 2's Contract C exactly)

```json
{
  "source_region": { "latitude": 20.48, "longitude": 67.52, "radius_km": 22, "backtrack_hours": 24 },
  "candidates": [
    {
      "mmsi": "419001234", "imo": "9123456", "name": "MV Ocean Star", "vessel_type": "Tanker",
      "position": { "latitude": 20.15, "longitude": 67.10 },
      "track": [[19.70, 66.40], [19.85, 66.70], [20.00, 66.90], [20.15, 67.10]],
      "evidence": {
        "min_distance_nm": 3.2, "hours_since_passage": 5.1, "heading_delta_deg": 12,
        "sog_at_closest_knots": 1.4, "intersects_source_region": true, "track_continuity": "continuous"
      }
    },
    {
      "mmsi": "419005678", "imo": "9007654", "name": "MT Gujarat Pearl", "vessel_type": "Cargo",
      "position": { "latitude": 21.10, "longitude": 67.70 },
      "track": [[21.40, 67.20], [21.30, 67.35], [21.20, 67.55], [21.10, 67.70]],
      "evidence": {
        "min_distance_nm": 14.6, "hours_since_passage": 9.8, "heading_delta_deg": 41,
        "sog_at_closest_knots": 9.2, "intersects_source_region": false, "track_continuity": "gapped"
      }
    }
  ]
}
```

## 3. Evidence variables and why each moves the score

| Signal | Direction |
|---|---|
| Environmental consistency (inside origin corridor) | Strong positive if inside; sharply reduced if outside — treat as near-gate-like |
| Distance to inferred origin | Closer → higher; normalise against the corridor radius, not a fixed distance |
| Time consistency | Track present within the plausible origin window → higher; hours after the window → weak |
| Heading compatibility | Small angle between vessel heading and bearing-to-origin → higher |
| Speed consistency | Weak/soft evidence only — near-zero SOG near the site/time can indicate loitering |
| Vessel type | Tanker/cargo get a soft contextual boost — **never a hard filter**; non-tankers can still spill bunker fuel |
| Track continuity | Continuous track → higher; large gaps are a soft red flag (possible AIS shutoff), not automatic guilt |

## 4. Model choice

| Approach | Explainability | Build difficulty | Verdict |
|---|---|---|---|
| **Weighted linear scoring** | High | Low | **Baseline — build this first** |
| Bayesian/likelihood refinement | Medium-high | Medium | Stretch, only if baseline finishes early |
| Bayesian network / PGM | Medium | High | Not realistic for this timeline |
| Graph/GNN | Low (for judges) | Very high | Needs training data we don't have — skip |

A weighted sum is chosen deliberately over anything fancier: a judge asking "why this vessel" gets
answered in one sentence per feature. A Bayesian network needs calibrated priors we have no data
to set honestly overnight — made-up priors would hurt credibility more than a transparent weighted
model helps.

## 5. Scoring formula

```
score(vessel) = wd·f_distance + wt·f_time + wh·f_heading + ws·f_speed
              + wtype·f_type + wc·f_continuity + wenv·f_env_consistency
```

Starting weights (tune after seeing Phase 2's real evidence, but don't spend time "learning" them
tonight — hand-set and openly stated is fine):

| Feature | Weight | Rationale |
|---|---|---|
| Environmental consistency | 0.25 | Near-gate signal — outside the corridor should suppress the whole score |
| Distance to inferred origin | 0.20 | Core spatial evidence |
| Time consistency | 0.20 | Core temporal evidence |
| Track continuity | 0.15 | Penalises suspicious AIS gaps |
| Heading compatibility | 0.10 | Supporting motion evidence |
| Speed consistency | 0.05 | Weak/soft evidence only |
| Vessel type | 0.05 | Contextual nudge, never a hard filter |

Normalise each sub-feature to 0–1 before applying weights (e.g. `f_distance = max(0, 1 -
min_distance_nm / radius_nm)`); final score = weighted sum × 100, clamped to [0, 100].

## 6. Reason-string generation

Pick the 1–2 highest-contributing sub-scores and render a template sentence, e.g.:

> "Passed within {min_distance_nm} nm of the backtracked source region {hours_since_passage} hours
> before detection."

Keep it factual and specific — never "this vessel is responsible."

## 7. Output contract (own this)

```json
{
  "spill_id": "SPILL-001",
  "ranked_vessels": [
    {
      "mmsi": "419001234",
      "name": "MV Ocean Star",
      "vessel_type": "Tanker",
      "confidence": 79,
      "reason": "Passed within 3.2 nm of the backtracked source region 5 hours before detection.",
      "sub_scores": {
        "environmental_consistency": 0.9, "distance": 0.85, "time_consistency": 0.7,
        "track_continuity": 0.8, "heading": 0.75, "speed": 0.6, "vessel_type": 1.0
      }
    }
  ]
}
```

`ranked_vessels` must be pre-sorted descending by `confidence` — don't push that requirement onto
the dashboard.

## 8. Novelty positioning (for the pitch, not code)

CleanSeaNet (EMSA) and Cerulean (SkyTruth) already combine satellite detection with AIS-based
vessel scoring operationally — "we combine satellites and AIS" is not a defensible novelty claim
on its own. The defensible gap this module owns:

> Explainable, per-feature-scored attribution (a visible breakdown, not a black-box output),
> tuned for Indian waters via INCOIS/Copernicus context — open and student-buildable, where
> CleanSeaNet is a closed European operational service and Cerulean is a global tool not tuned to
> Indian coastal traffic.

## 9. Testing without any other phase

Write the scoring function as a pure function of the mock JSON in §2 and unit-test it with
`pytest`: confidence scores must be in [0, 100], `ranked_vessels` must come out sorted, and the
vessel intersecting the origin region with the shortest `hours_since_passage` should always
outrank one that doesn't intersect it at all, regardless of weight tuning.

## 10. Guardrail

Every score is presented as **probable attribution**, never "the vessel responsible." State
explicitly in the pitch that weights are hand-set from domain reasoning, not learned — this is
honest and still a defensible choice for a one-night prototype.
