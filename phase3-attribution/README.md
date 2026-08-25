# Phase 3 — Attribution Engine (Evidence Fusion & Ranking)

**Problem Statement:** SIH26143 — Satellite Oil-Spill Detection & AIS Vessel Attribution  
**Module Owner:** Om  
**Role:** Consumes backtracked candidate vessel evidence (Contract C) and outputs explainable, per-feature-scored vessel rankings with confidence ratings and factual reasons (Contract D).

---

## 1. Quick Start

### Installation
`ash
pip install -r requirements.txt
`

### Run on Mock Data
`ash
# Print formatted Contract D output to stdout
python cli.py --mock --pretty

# Run with Bayesian Likelihood refinement
python cli.py --mock --pretty --method bayesian
`

### Run on Real Contract C JSON
`ash
python cli.py -i path/to/backtrack_output.json -o path/to/attribution_output.json --spill-id SPILL-001 --pretty
`

### Run Unit Tests
`ash
pytest tests/ -v
`

---

## 2. Evidence Signals & Normalization

| Signal | Feature Key | Weight | Normalization / Rationale |
|---|---|---|---|
| **Environmental Consistency** | environmental_consistency | **0.25** | Near-gate signal: .0$ if vessel track intersects origin circle, sharp penalty outside. |
| **Distance to Origin** | distance | **0.20** | Normalized against dynamic corridor radius: $\max(0, 1 - d / R_{\text{nm}})$. |
| **Time Consistency** | 	ime_consistency | **0.20** | Elapsed hours relative to backtrack window: $\max(0, 1 - \Delta t / T_{\text{max}})$. |
| **Track Continuity** | 	rack_continuity | **0.15** | Continuous (.9$), Gapped (.4$), Unknown (.5$). Penalizes suspicious transponder shutoff. |
| **Heading Compatibility** | heading | **0.10** | Angular delta relative to drift vector: $\max(0, 1 - \Delta\theta / 180^\circ)$. |
| **Speed Consistency** | speed | **0.05** | Loitering / low maneuvering speed (-3\text{ kts}$) yields .90$, high cruise yields .30$. |
| **Vessel Type Prior** | essel_type | **0.05** | Tanker (.0$), Cargo (.7$), Tug (.6$), Fishing/Other (.4$). Soft multiplier, never a hard filter. |

---

## 3. Output Guarantee (Contract D)

- **Pre-sorted**: Always sorted descending by confidence ([0-100]).
- **Explainability**: Every vessel carries complete sub_scores breakdown.
- **Factual Reason String**: Human-readable narrative citing distance, time, and track metrics.
- **Strict Guardrails**: Presents findings as **probable attribution triage**, never asserting criminal or legal certainty.

---

## 4. Pitch Talking Points & Defense

1. **Why not a black-box Neural Network / GNN?**
   - Juries and maritime authorities require transparent auditability. If asked *"Why was vessel X flagged?"*, our engine provides the exact per-feature numerical contribution.
2. **Defensible Novelty:**
   - Where CleanSeaNet (EMSA) is closed and European, and Cerulean (SkyTruth) is global and non-explainable, our platform provides open, drift-aware, explainable attribution tuned for the Indian Ocean and Arabian Sea.
