# SKILLS — Stack, Libraries & Accounts Per Phase

Setup this once per machine, not per phase — but each phase only needs its own row.

## Global

- Python 3.10+
- Git
- A free text editor / Antigravity workspace per phase

## Phase 1 — Satellite Detection (Martin)

| Need | Choice |
|---|---|
| Framework | PyTorch |
| Segmentation | Custom U-Net (or `segmentation_models_pytorch`) |
| Raster/geo | `rasterio` (only if working from raw GeoTIFF; not needed if starting from the SOS benchmark) |
| Viz | `matplotlib` |
| Dataset | Deep-SAR Oil Spill (SOS) Sentinel-1 subset — Zenodo (refined 2025 version preferred if download is practical) |
| Accounts needed | None to start (SOS is a direct download). Copernicus Data Space account only needed if pulling fresh raw Sentinel-1 scenes later. |

```bash
pip install torch torchvision segmentation-models-pytorch rasterio matplotlib numpy pillow
```

## Phase 2 — AIS / GIS / Backtracking (Jitaan)

| Need | Choice |
|---|---|
| Geo containers | `geopandas`, `shapely`, `pyproj` |
| Trajectories | `movingpandas` |
| Raster (conditional) | `rasterio` — only if the spill mask arrives as GeoTIFF instead of polygon/GeoJSON |
| Live AIS | AISstream.io — free API key, WebSocket (`wss://stream.aisstream.io/v0/stream`) |
| AIS cross-check | Global Fishing Watch API — free registered token |
| AIS dev/offline dataset | Danish Maritime Authority historical AIS CSV — no login, direct HTTPS download |
| Wind/current (self-serve, no key) | Open-Meteo Weather Forecast API + Marine Weather API |
| Wind/current fallback | NASA PO.DAAC OSCAR (requires Earthdata login — only if Open-Meteo coverage is too coarse) |

```bash
pip install geopandas shapely pyproj movingpandas requests websockets pandas numpy
```

Accounts to create tonight: AISstream.io (instant), Global Fishing Watch (instant, free).
Open-Meteo needs no signup at all — use it first if Phase 4's Copernicus pipeline isn't ready yet.

## Phase 3 — Attribution Engine (Om)

| Need | Choice |
|---|---|
| Language | Python |
| Scoring | Plain Python / `numpy` — no ML framework required for the weighted-sum baseline |
| Stretch | `scipy.stats` or hand-rolled likelihood updates if attempting the Bayesian refinement |
| Testing | `pytest` for scoring-function unit tests against the mock vessel list |
| Accounts needed | None |

```bash
pip install numpy pytest
```

## Phase 4 — Environmental Data + Dashboard (Rudra)

| Need | Choice |
|---|---|
| Env data (primary) | Copernicus Marine Service — `copernicusmarine` Python toolbox (free account required) |
| Env data (backup) | NOAA ERDDAP (no account) |
| Env data (India validation) | INCOIS Data Holdings (access varies by product — verify before promising) |
| Map | Leaflet.js (CDN, no build step) |
| Frontend | Plain HTML/CSS/JS (React optional if the team prefers, via `react-leaflet`) |
| Backend (optional) | FastAPI, if serving the merged JSON from a real endpoint rather than a static file |

```bash
pip install copernicusmarine xarray netcdf4 fastapi uvicorn
```

Accounts to create tonight: Copernicus Marine (free). NOAA ERDDAP and Leaflet need nothing.

## Verified dataset/prior-art repos worth cloning for reference

- `github.com/chashmishcoder/Oil-Spill-Detection` — U-Net + AIS DBSCAN anomaly reference
- `github.com/oceanhackweek/ohw23_proj_oil` — fast SAR exploratory baseline notebooks
- `github.com/josna-14/Maritime_Vessel_Tracking` — React/Leaflet AIS map reference
- `github.com/PaulLeCam/react-leaflet` — if Phase 4 goes React instead of plain HTML

Verify license before copying code wholesale from any of the above; treat them as reference, not
as a base to fork directly, unless the license is confirmed compatible.
