# Phase 3 - Attribution Engine: Pitch and Jury Defense Cheat-Sheet

**Prepared for:** Om | SIH26143 Hackathon Defense
**Module:** Multi-Evidence Vessel Attribution & Ranking Engine

---

## 1. The 30-Second Elevator Pitch

> Detection tells you that oil is on the water; backtracking tells you where it came from. Our module answers the most critical investigative question: **Why this vessel and not that one?**
>
> We ingest the drift-backtracked origin corridor and AIS tracks to perform explainable, multi-evidence fusion across 7 distinct kinematic and environmental signals. Rather than an unexplainable black-box, each candidate receives a transparent 0-100 attribution confidence with an exact sub-score breakdown and human-readable justification tailored for Indian coastal surveillance.

---

## 2. Anticipated Jury Questions & Defensible Answers

### Q1: Why not use a Deep Learning model or Graph Neural Network (GNN) for vessel ranking?
**Answer:**
1. **Auditability & Legal Scrutiny:** In maritime law enforcement (e.g., Indian Coast Guard / DG Shipping), black-box outputs cannot justify initiating an investigation. Maritime authorities need to inspect why a ship was flagged (e.g., CPA of 1.8 nm, 3 hours prior to slick detection, loitering SOG).
2. **Data Calibration Honesty:** There is no massive ground-truth training dataset of confirmed vessel-slick spills in Indian waters. Training a GNN overnight would produce ungrounded hallucinated priors. A transparent, domain-grounded weighted linear model with Bayesian likelihood validation is scientifically honest and fully explainable.

---

### Q2: How is this different from existing tools like CleanSeaNet or SkyTruth Cerulean?
**Answer:**
- **CleanSeaNet (EMSA):** Closed European operational service; non-public algorithms; restricted to EU waters. SlickMesh AI is an open, student-deployable architecture tuned specifically for the Arabian Sea & Bay of Bengal.
- **Cerulean (SkyTruth):** Global satellite-only focus; uses slick-path alignment without open, granular per-feature scoring weights. SlickMesh AI provides a granular 7-factor evidence breakdown with explicit drift-backtracking corridor gating.

---

### Q3: Does your system prove that a vessel is legally guilty of an oil spill?
**Answer:**
> **No, and by design it should not.**
> SAR satellite imagery detects surface-roughness anomalies, not chemical hydrocarbon fingerprints. AIS shows proximity and trajectory, not direct observation of a discharge valve. Therefore, our output is strictly calibrated as **probabilistic triage** to help maritime authorities prioritize inspection resources, not to deliver a legal verdict.

---

## 3. Evidence Signals & Weights Breakdown

Confidence = clamp(round(100 * sum(w_i * f_i)), 0, 100)

| Signal | Weight | Role & Domain Rationale |
|---|---|---|
| **Environmental Consistency** | **0.25** | Near-gate factor: track intersection with drift-backtracked origin corridor. |
| **Distance to CPA** | **0.20** | Normalized against adaptive corridor radius R_nm, ensuring fair scale invariance. |
| **Time Consistency** | **0.20** | Passage proximity relative to hydrodynamic backtrack window. |
| **Track Continuity** | **0.15** | Penalizes transponder blackouts (potential AIS spoofing/shutoff near slick site). |
| **Heading Compatibility** | **0.10** | Alignment with drift axis / slick orientation. |
| **Speed Consistency** | **0.05** | Identifies loitering / anomalous slow maneuvering (0-3 kts). |
| **Vessel Type Prior** | **0.05** | Soft contextual boost for Tankers (1.0), Cargo (0.7), without hard exclusion. |

---

## 4. Live CLI Demonstration Commands

`ash
# 1. Clean live demo summary table with top drivers
python cli.py --mock --table --explain

# 2. Print JSON Contract D to stdout
python cli.py --mock --pretty
`
