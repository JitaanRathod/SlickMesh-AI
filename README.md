# SLICKMESH-AI (SIH26143)
### Autonomous Spaceborne SAR Oil Spill Detection, Hydrodynamic Backtracking & Explainable Vessel Attribution Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![PyTorch U-Net](https://img.shields.io/badge/deep--learning-PyTorch%20U--Net-EE4C2C.svg)](https://pytorch.org)
[![Tests: 31 Passing](https://img.shields.io/badge/tests-31%2F31%20passing-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 1. Executive Summary & Problem Statement
Under **Smart India Hackathon 2026 (Problem Statement SIH26143)**, maritime law enforcement agencies (Indian Coast Guard, Directorate General of Shipping, and Port State Control) face a critical operational challenge: **identifying which commercial vessel is responsible for marine hydrocarbon discharges detected in wide-area satellite radar passes**.

Conventional approaches either detect surface oil slicks without attributing source vessels, or track AIS positions without accounting for oceanographic drift physics. **SlickMesh-AI** delivers an end-to-end **4D Maritime Forensic Evidence Chain** ($Space + Time + Physics + Evidence$) that:
1. **Detects** candidate oil slicks from all-weather **Copernicus Sentinel-1 C-Band Synthetic Aperture Radar (SAR)** using a deep convolutional **U-Net** semantic segmentation model.
2. **Reconstructs** probable release coordinates and emission time horizons by reversing ocean current vectors and **3% empirical windage drift** physics (Lagrangian hindcast).
3. **Filters & Attributes** passing AIS vessel trajectories using a **4-stage filtering funnel** and a **7-signal multi-factor evidence engine** (`normalizers.py`, `engine.py`, `explainer.py`).
4. **Verifies & Explains** attribution decisions with plain-English legal dossiers, raw-to-normalized evidence matrices, observed vs reconstructed validation metrics, and interactive 4D scenario replays.

```text
                               SLICKMESH-AI 4D MARITIME FORENSICS
                                               │
                                               ▼
               ┌───────────────────────────────────────────────────────────────┐
               │ PHASE 1: SPACEBORNE SAR DETECTION & QC                        │
               │ Sentinel-1 C-SAR → Preprocessing → PyTorch U-Net → Geometry   │
               └───────────────────────────────┬───────────────────────────────┘
                                               │ [Contract A: Slick Polygon, Centroid, Area km²]
                                               ▼
               ┌───────────────────────────────────────────────────────────────┐
               │ PHASE 2: SPATIO-TEMPORAL RECONSTRUCTION & AIS BACKTRACKING   │
               │ Metocean Ingestion → Lagrangian 3% Windage → Origin Corridor  │
               └───────────────────────────────┬───────────────────────────────┘
                                               │ [Contract B: Origin Corridor + Candidate AIS Tracks]
                                               ▼
               ┌───────────────────────────────────────────────────────────────┐
               │ PHASE 3: 7-SIGNAL EVIDENCE FUSION & EXPLAINABLE ATTRIBUTION  │
               │ Signal Normalizers → Multi-Factor Scorer → Natural Explainer  │
               └───────────────────────────────┬───────────────────────────────┘
                                               │ [Contract C: Ranked Suspect Dossiers + Evidence Matrix]
                                               ▼
               ┌───────────────────────────────────────────────────────────────┐
               │ PHASE 4: FORENSIC INVESTIGATION WORKSPACE & AUDIT DOSSIERS    │
               │ 4D Timeline Replay → IoU Validation → 17-Point Audit Brief   │
               └───────────────────────────────────────────────────────────────┘
```

---

## 2. 4-Phase System Architecture

### Phase 1: Multi-Mission Spaceborne Remote Sensing & Quality Control (`phase1-satellite/`)
- **Multi-Mission Constellation:**
  - **ESA Copernicus Sentinel-1:** C-Band Synthetic Aperture Radar ($5.405\text{ GHz}$), Level-1 IW GRD ($5\text{m} \times 20\text{m}$), all-weather day/night sea surface roughness damping.
  - **ISRO EOS-04 / RISAT-1A:** Spaceborne C-Band SAR ($5.35\text{ GHz}$), circular & linear quad-polarimetry ($3\text{m} - 50\text{m}$ resolution) for sovereign Indian EEZ rapid revisit passes.
  - **ISRO EOS-06 / Oceansat-3:** Ocean Colour Monitor (OCM-3, 13 bands) + Sea Surface Temperature Monitor (SSTM-1) for distinguishing biogenic algal blooms from mineral hydrocarbons via chlorophyll absorption and thermal skin contrast ($\Delta T \approx -0.4\text{ K}$).
  - **ESA Copernicus Sentinel-2:** High-resolution ($10\text{m}$) Multi-Spectral Instrument (MSI) optical & sunglint reflectance validation during cloudless daylight scenes.
- **Architecture:** PyTorch deep semantic segmentation **U-Net** (`weights/unet_best.pth`), featuring 4 encoder downsampling blocks with skip connections and 4 decoder upsampling blocks.
- **Preprocessing:** Radiometric calibration, speckle Lee filtering, decibel log-scaling ($\sigma^0$), and adaptive Otsu dark-patch thresholding.
- **Environmental QC & Look-Alike Screening:** Automatic rejection of low-wind ($<2.0\text{ m/s}$) specular reflections, high-wind ($>12.0\text{ m/s}$) slick dispersion flags, and Bonn Agreement oil thickness volume estimation ($1 - 10\text{ m}^3/\text{km}^2$).
- **Data Output:** Standardized `Contract A` (`contract_a_output.json`).

### Phase 2: Spatio-Temporal Reconstruction & Hydrodynamics (`phase2-ais-gis/`)
- **Dual Oceanographic Feeds:** Ingestion toggle between **INCOIS Ocean State Forecasts (OSF)** (high-resolution Indian Ocean regional hydrodynamic model) and **Copernicus Marine / ECMWF Global Reanalysis**.
- **Hydrodynamic Reverse Drift:** Computes net particle drift velocity:
  $$\vec{V}_{\text{drift}} = \vec{V}_{\text{current}} + 0.03 \cdot \vec{V}_{\text{wind}}$$
  Reverses displacement over backtrack horizon $\Delta T \in [6\text{h}, 72\text{h}]$:
  $$\vec{D}_{\text{origin}} = -\vec{V}_{\text{drift}} \cdot \Delta T$$
- **Adaptive Origin Corridor:** Radius dynamically accounts for cumulative wind dispersion:
  $$R_{\text{corridor}} = 10.0\text{ km} + \frac{0.5 \cdot |\vec{V}_{\text{wind}}| \cdot \Delta T}{10.0}$$
- **AIS & GIS Data Fusion:** Unified cache ingesting live WebSocket streams (`AISstream.io`), Open European AIS, and an authentic database of 100+ Indian EEZ merchant vessels (`gis_database.py`).
- **Data Output:** Standardized `Contract B` (`output/contract_c.json`).

### Phase 3: Explainable Attribution Engine (`phase3-attribution/`)
- **Raw Evidence Extraction:** Computes Closest Point of Approach (CPA distance in nautical miles), time delta since passage, heading delta vs slick axis, transit speed over ground (SOG), AIS transponder continuity, and vessel risk classification.
- **Signal Normalizers (`src/normalizers.py`):** Converts non-linear physical dimensions into normalized probability features $[0.0, 1.0]$.
- **7-Signal Multi-Factor Scoring Formulation (`src/engine.py`):**
  $$\text{Evidence Score} = \sum_{i=1}^{7} w_i \cdot S_i$$
  $$\text{Weights: } w_{\text{corridor}} = 0.25, w_{\text{dist}} = 0.20, w_{\text{time}} = 0.20, w_{\text{continuity}} = 0.15, w_{\text{heading}} = 0.10, w_{\text{speed}} = 0.05, w_{\text{vessel\_type}} = 0.05$$
- **Natural Language Explainer (`src/explainer.py`):** Synthesizes human-readable legal assessments, qualitative signal strength tags (*Strong*, *Moderate*, *Weak*), supporting evidence points, and counter-evidence / uncertainty factors.
- **Data Output:** Standardized `Contract C` (`ranked_vessels`).

### Phase 4: Forensic Workspace & Investigation Briefs (`dashboard/`, `server.py`)
- **Forensic 4D Timeline Replay:** Interactive chronological time slider ($T-24\text{h} \rightarrow T=0\text{h}$) with Lagrangian particle plume dispersion and vessel trajectory interpolation.
- **Observed vs Reconstructed Validation:** Real-time Intersection over Union (IoU) spatial overlap and centroid offset error ($1.8\text{ km}$).
- **1-Click GeoJSON GIS Export:** Standard RFC 7946 GeoJSON export endpoint (`/api/export-geojson`) for instantaneous loading into QGIS, ArcGIS, and Coast Guard MRCC command consoles.
- **17-Point Audit Brief Generator:** Automated generation of print-ready and markdown investigation reports formatted under **IMO MARPOL 73/78 Annex I** and **UNCLOS Article 217**.
- **Data Output:** Standardized `Contract E` (`dashboard/incident.json`).

---

## 3. 4-Stage Candidate Filtering Funnel

Rather than scoring hundreds of vessels blindly, SlickMesh-AI applies a rigorous 4-stage geographic and temporal funnel:

```text
┌────────────────────────────────────────────────────────┐
│ 1. TOTAL BASIN FLEET INGESTED                          │ 427+ Active Vessels
│    Real-time AIS streams + Indian EEZ database         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 2. SPATIAL CORRIDOR INTERSECT FILTER                   │ 38 Vessels
│    Traversed within adaptive origin corridor radius    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 3. TEMPORAL WINDOW ALIGNMENT                           │ 11 Vessels
│    Within estimated release window (T - 24h)           │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 4. 7-SIGNAL KINEMATIC & EVIDENCE SCORING               │ 4 Scored Candidates
│    Multi-factor evidence vector computation            │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ PRIMARY INVESTIGATIVE LEAD IDENTIFIED                  │ Rank #1 Suspect (e.g. 89%)
└────────────────────────────────────────────────────────┘
```

---

## 4. Evidence Matrix & Signal Normalization

| Signal Dimension | Raw Observation Range | Normalization Function (`normalizers.py`) | Normalizer Score Range | Evidence Weight ($w_i$) |
|:---|:---|:---|:---|:---|
| **Corridor Overlap** | True / False (Geometric intersection) | Boolean intersection check | $1.00\text{ or }0.00$ | **25%** |
| **CPA Distance** | $0.0 \rightarrow 30.0\text{ nm}$ | Linear decay: $\max(0, 1 - \frac{d}{30})$ | $0.00 \rightarrow 1.00$ | **20%** |
| **Temporal Delta** | $0.0 \rightarrow 24.0\text{ hrs}$ | Quadratic decay: $\max(0, 1 - (\frac{\Delta t}{24})^2)$ | $0.00 \rightarrow 1.00$ | **15%** |
| **AIS Continuity** | Continuous / Blackout Gap | Continuous = 1.0, Gap = 0.63 | $0.63 \rightarrow 1.00$ | **15%** |
| **Heading Alignment**| $0^\circ \rightarrow 90^\circ$ delta | Cosine decay: $\cos(\Delta \theta)$ | $0.00 \rightarrow 1.00$ | **10%** |
| **Speed Profile** | $0.0 \rightarrow 25.0\text{ kts}$ | Gaussian bell: $e^{-\frac{(v - v_{\text{ideal}})^2}{2\sigma^2}}$ | $0.00 \rightarrow 1.00$ | **8%** |
| **Vessel Risk** | Crude Tanker, Cargo, Tug | Cargo risk mapping: Tanker = 0.95, Cargo = 0.60 | $0.30 \rightarrow 0.95$ | **7%** |

---

## 5. Built-in Deterministic Maritime Scenarios (`scenarios.py`)

To ensure repeatable, judge-ready demonstrations without reliance on live network connectivity, SlickMesh-AI includes 5 pre-configured maritime cases:

1. **Arabian Sea Oilfield Spill (Mumbai High ONGC Complex):**
   - *Target:* $19.42^\circ\text{N}, 71.35^\circ\text{E}$
   - *Scenario:* Tanker collision & pipeline overflow in high-density crude shipping fairway.
   - *Primary Suspect:* `Al-Bahar Crude` (MMSI: `419001111`, Score: `89%`).
2. **MARPOL Annex I Illegal Bilge Discharge:**
   - *Target:* $18.85^\circ\text{N}, 71.10^\circ\text{E}$
   - *Scenario:* Operational bilge water discharge creating a linear $9.2\text{ km}^2$ slick.
   - *Primary Suspect:* `Pacific Vanguard` (MMSI: `352001944`, Score: `92%`).
3. **Dark Ship & AIS Discontinuity (Blackout Gap):**
   - *Target:* $16.50^\circ\text{N}, 72.00^\circ\text{E}$
   - *Scenario:* Deliberate AIS transponder blackout during illegal tank washing.
   - *Primary Suspect:* `Shadow Trader` (MMSI: `419099999`, Score: `88%`).
4. **Bay of Bengal KG-D6 Deepwater Basin:**
   - *Target:* $16.15^\circ\text{N}, 82.55^\circ\text{E}$
   - *Scenario:* Multi-vessel convergence zone near deepwater FPSO installations.
   - *Primary Suspect:* `Bay Explorer` (MMSI: `419004444`, Score: `85%`).
5. **Gulf of Khambhat / Alang Anchorage:**
   - *Target:* $20.48^\circ\text{N}, 67.52^\circ\text{E}$
   - *Scenario:* Shipbreaking fairway and anchorage waiting area.
   - *Primary Suspect:* `MV Ocean Star` (MMSI: `419001234`, Score: `84%`).

---

## 6. Directory Structure

```text
SlickMesh-AI/
├── phase1-satellite/           # Phase 1: SAR Acquisition & U-Net Segmentation
│   ├── detect.py               # U-Net inference & contour extraction
│   ├── unet.py                 # PyTorch model architecture
│   ├── train.py                # Model training script
│   └── weights/unet_best.pth   # Trained PyTorch U-Net checkpoint
├── phase2-ais-gis/             # Phase 2: AIS Ingestion & Hydrodynamic Backtracker
│   ├── src/backtracker.py      # Lagrangian reverse drift solver
│   ├── src/trajectory_builder.py # AIS multi-waypoint track constructor
│   ├── src/candidate_matcher.py  # Spatio-temporal corridor intersection matcher
│   └── src/ais_listener.py     # Live AISstream.io WebSocket client
├── phase3-attribution/         # Phase 3: Evidence Engine & Normalizers
│   ├── src/engine.py           # 7-Signal scoring orchestrator
│   ├── src/normalizers.py      # Non-linear feature normalization functions
│   ├── src/explainer.py        # Natural language legal attribution generator
│   └── src/scenarios.py        # 5 Deterministic evaluation case scenarios
├── tests/                      # Master Unit & Integration Test Suites
│   ├── test_integration_master.py # Master end-to-end integration test suite
│   └── test_*.py               # Phase 1, 2, and 3 unit tests (31/31 passed)
├── gis_database.py             # 100+ Indian EEZ vessels, IMO TSS lanes, EEZ boundary
├── server.py                   # FastAPI REST API Gateway & Dashboard Server
├── run_pipeline.py             # Unified CLI entrypoint
├── index.html                  # SlideX Modern SaaS Tactical Web Console
├── app.js                      # Leaflet.js GIS map logic & forensic timeline
├── style.css                   # SaaS Light design system stylesheet
└── contract_a_output.json      # Standardized Contract A output
```

---

## 7. Installation & Quickstart

### Prerequisites
- Python 3.10 or higher
- Git

### 1. Clone & Install Dependencies
```powershell
git clone https://github.com/JitaanRathod/SlickMesh-AI.git
cd SlickMesh-AI
python -m pip install -r requirements.txt
python -m pip install -r phase3-attribution/requirements.txt
```

### 2. Run Master Test Suite (31/31 Tests)
```powershell
python -m pytest tests/ -v
python -m pytest phase3-attribution/tests/ -v
```

### 3. Launch Tactical Web Console
```powershell
python server.py
```
Open your browser at **`http://127.0.0.1:8000`**.

### 4. Run CLI Pipeline Execution
```powershell
# Run Mumbai High scenario
python run_pipeline.py --scenario mumbai --wind-speed 6.8 --backtrack 18

# Run Dark Ship blackout scenario
python run_pipeline.py --scenario dark_ship --wind-speed 7.2 --backtrack 24
```

---

## 8. Statutory & Regulatory Standards
- **IMO MARPOL 73/78 Annex I:** Regulations for the Prevention of Pollution by Oil.
- **UNCLOS Article 217:** Enforcement by Flag and Coastal States over EEZ and Territorial Waters.
- **EMSA CleanSeaNet & NOAA GNOME:** Guidelines for spaceborne SAR slick identification and 3% Lagrangian windage modeling.

---

## 9. Contributors & Hackathon Track
- **Project:** SlickMesh-AI (SIH26143)
- **Problem Statement:** Satellite Oil Spill Detection & AIS-Based Vessel Attribution
- **Repository:** [https://github.com/JitaanRathod/SlickMesh-AI](https://github.com/JitaanRathod/SlickMesh-AI)
