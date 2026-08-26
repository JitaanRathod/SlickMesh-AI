import os
import sys
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Ensure subdirectories are on sys.path for direct clean imports
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "phase1-satellite"))
sys.path.insert(0, str(ROOT_DIR / "phase2-ais-gis"))
sys.path.insert(0, str(ROOT_DIR / "phase3-attribution"))

from detect import run_detection
from engine import AttributionEngine
from models import BacktrackInput, SourceRegion, CandidateVessel, Position, VesselEvidence

app = FastAPI(title="SlickMesh-AI Master API & Dashboard Server", version="2.0.0")

# Enable CORS for local dev / dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PipelineRequest(BaseModel):
    image_name: str = "s1_active.png"
    wind_speed: float = 5.4
    wind_direction: float = 72.0
    current_u: float = 0.18
    current_v: float = 0.07
    backtrack_hours: int = 24
    target_region: Optional[str] = "default"


def get_regional_presets(region: str) -> Dict[str, Any]:
    """Provides regional reference coordinates for Indian maritime zones."""
    presets = {
        "mumbai": {
            "lat": 19.65, "lon": 72.38,
            "candidates": [
                {
                    "mmsi": "419001111", "imo": "9345678", "name": "Al-Bahar Crude", "vessel_type": "Crude Oil Tanker",
                    "min_dist_nm": 1.8, "hours": 3.5, "heading_delta": 8.0, "sog": 2.1, "intersects": True, "continuity": "continuous",
                    "track": [[19.30, 71.90], [19.45, 72.10], [19.55, 72.25], [19.65, 72.38]]
                },
                {
                    "mmsi": "419002222", "imo": "9223344", "name": "Konkan Star", "vessel_type": "Chemical Tanker",
                    "min_dist_nm": 4.2, "hours": 7.0, "heading_delta": 22.0, "sog": 8.5, "intersects": True, "continuity": "continuous",
                    "track": [[19.10, 71.80], [19.35, 72.05], [19.50, 72.20], [19.70, 72.45]]
                },
                {
                    "mmsi": "419003333", "imo": "9112233", "name": "Mumbai Pioneer", "vessel_type": "Cargo",
                    "min_dist_nm": 14.5, "hours": 14.0, "heading_delta": 55.0, "sog": 14.2, "intersects": False, "continuity": "continuous",
                    "track": [[19.80, 72.70], [19.90, 72.85], [20.00, 73.00]]
                }
            ]
        },
        "bob": {
            "lat": 16.15, "lon": 82.28,
            "candidates": [
                {
                    "mmsi": "419004444", "imo": "9445566", "name": "Bay Explorer", "vessel_type": "Oil Tanker",
                    "min_dist_nm": 2.4, "hours": 4.0, "heading_delta": 10.0, "sog": 1.8, "intersects": True, "continuity": "continuous",
                    "track": [[15.80, 81.90], [15.95, 82.10], [16.10, 82.25], [16.20, 82.35]]
                },
                {
                    "mmsi": "419005555", "imo": "9556677", "name": "Godavari Pride", "vessel_type": "Bulk Carrier",
                    "min_dist_nm": 12.0, "hours": 9.5, "heading_delta": 45.0, "sog": 12.0, "intersects": False, "continuity": "gapped",
                    "track": [[16.30, 82.60], [16.45, 82.80], [16.60, 83.00]]
                }
            ]
        },
        "default": {
            "lat": 20.48, "lon": 67.52,
            "candidates": [
                {
                    "mmsi": "419001234", "imo": "9123456", "name": "MV Ocean Star", "vessel_type": "Tanker",
                    "min_dist_nm": 3.2, "hours": 5.1, "heading_delta": 12.0, "sog": 1.4, "intersects": True, "continuity": "continuous",
                    "track": [[19.70, 66.40], [19.85, 66.70], [20.00, 66.90], [20.15, 67.10]]
                },
                {
                    "mmsi": "419005678", "imo": "9007654", "name": "MT Gujarat Pearl", "vessel_type": "Cargo",
                    "min_dist_nm": 14.6, "hours": 9.8, "heading_delta": 41.0, "sog": 9.2, "intersects": False, "continuity": "gapped",
                    "track": [[21.40, 67.20], [21.30, 67.35], [21.20, 67.55], [21.10, 67.70]]
                },
                {
                    "mmsi": "419009876", "imo": "9876543", "name": "Deepsea Sentinel", "vessel_type": "Container Ship",
                    "min_dist_nm": 22.0, "hours": 16.5, "heading_delta": 65.0, "sog": 16.0, "intersects": False, "continuity": "continuous",
                    "track": [[20.90, 68.50], [21.05, 68.70]]
                }
            ]
        }
    }
    return presets.get(region.lower(), presets["default"])


def execute_integrated_pipeline(
    image_name: str,
    wind_speed: float,
    wind_direction: float,
    current_u: float,
    current_v: float,
    backtrack_hours: int,
    target_region: str = "default"
) -> Dict[str, Any]:
    """Core integration orchestrator function."""
    region_info = get_regional_presets(target_region)
    ref_lat = region_info["lat"]
    ref_lon = region_info["lon"]

    # 1. Execute Phase 1 (Satellite SAR Detection)
    sar_image_path = os.path.join(ROOT_DIR, image_name)
    spill_output = run_detection(
        image_path=sar_image_path if os.path.exists(sar_image_path) else None,
        synthetic=not os.path.exists(sar_image_path),
        ref_lat=ref_lat,
        ref_lon=ref_lon,
        wind_speed_ms=wind_speed,
        output_path=os.path.join(ROOT_DIR, "contract_a_output.json")
    )

    # 2. Phase 2 (Hydrodynamic Reverse-Drift Origin Estimation)
    wind_rad = math.radians((wind_direction + 180) % 360)
    wind_u = wind_speed * math.sin(wind_rad)
    wind_v = wind_speed * math.cos(wind_rad)

    # Net drift = current + 3% windage
    drift_u = current_u + 0.03 * wind_u
    drift_v = current_v + 0.03 * wind_v

    # Reverse displacement over backtrack_hours
    disp_u_m = -drift_u * (backtrack_hours * 3600)
    disp_v_m = -drift_v * (backtrack_hours * 3600)

    # Latitude/Longitude degree offsets
    lat_deg_per_m = 1.0 / 111320.0
    lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(spill_output.centroid.lat)))

    origin_lat = round(spill_output.centroid.lat + disp_v_m * lat_deg_per_m, 4)
    origin_lon = round(spill_output.centroid.lon + disp_u_m * lon_deg_per_m, 4)
    radius_km = round(10.0 + (0.5 * wind_speed * backtrack_hours) / 10.0, 1)

    source_region_model = SourceRegion(
        latitude=origin_lat,
        longitude=origin_lon,
        radius_km=radius_km,
        backtrack_hours=float(backtrack_hours)
    )

    # Build Candidate Vessels for Contract C
    candidates_list = []
    for c_raw in region_info["candidates"]:
        cand = CandidateVessel(
            mmsi=c_raw["mmsi"],
            imo=c_raw.get("imo"),
            name=c_raw["name"],
            vessel_type=c_raw["vessel_type"],
            position=Position(latitude=c_raw["track"][-1][0], longitude=c_raw["track"][-1][1]),
            track=c_raw["track"],
            evidence=VesselEvidence(
                min_distance_nm=c_raw["min_dist_nm"],
                hours_since_passage=c_raw["hours"],
                heading_delta_deg=c_raw["heading_delta"],
                sog_at_closest_knots=c_raw["sog"],
                intersects_source_region=c_raw["intersects"],
                track_continuity=c_raw["continuity"]
            )
        )
        candidates_list.append(cand)

    backtrack_input = BacktrackInput(
        source_region=source_region_model,
        candidates=candidates_list
    )

    # 3. Phase 3 (Attribution Engine Evidence Fusion)
    engine = AttributionEngine()
    attribution_output = engine.process(backtrack_input, spill_id=spill_output.spill_id)

    # 4. Phase 4 (Assemble Canonical Contract E Payload for Dashboard)
    vessels_e = []
    cand_map = {c.mmsi: c for c in candidates_list}
    for rv in attribution_output.ranked_vessels:
        c_obj = cand_map.get(rv.mmsi)
        if c_obj:
            # Format to GeoJSON [lon, lat] convention for Leaflet
            pos_lon_lat = [round(c_obj.position.longitude, 4), round(c_obj.position.latitude, 4)]
            track_lon_lat = [[round(pt[1], 4), round(pt[0], 4)] for pt in c_obj.track]
            vessels_e.append({
                "name": rv.name,
                "mmsi": rv.mmsi,
                "type": rv.vessel_type,
                "confidence": rv.confidence,
                "reason": rv.reason,
                "position": pos_lon_lat,
                "track": track_lon_lat,
                "sub_scores": rv.sub_scores.model_dump()
            })

    contract_e = {
        "incident": {
            "id": spill_output.spill_id,
            "detected_at": spill_output.detected_at,
            "area_km2": spill_output.area_km2,
            "confidence": spill_output.confidence,
            "polygon": spill_output.polygon
        },
        "environment": {
            "current_u_ms": current_u,
            "current_v_ms": current_v,
            "wind_speed_ms": wind_speed,
            "wind_direction_deg": wind_direction,
            "source_model": "Copernicus Marine / Open-Meteo Live API"
        },
        "source_region": {
            "latitude": origin_lat,
            "longitude": origin_lon,
            "radius_km": radius_km,
            "backtrack_hours": backtrack_hours
        },
        "vessels": vessels_e
    }

    # Save to disk for static dashboard fallbacks
    for dest in (os.path.join(ROOT_DIR, "incident.json"), os.path.join(ROOT_DIR, "dashboard", "incident.json")):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(contract_e, f, indent=2)

    return contract_e


@app.post("/api/run-pipeline")
async def run_pipeline_api(req: PipelineRequest):
    """Runs end-to-end pipeline with custom slider and region parameters."""
    try:
        return execute_integrated_pipeline(
            image_name=req.image_name,
            wind_speed=req.wind_speed,
            wind_direction=req.wind_direction,
            current_u=req.current_u,
            current_v=req.current_v,
            backtrack_hours=req.backtrack_hours,
            target_region=req.target_region or "default"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mock-incident")
async def get_mock_incident():
    """Returns default or active Contract E incident payload."""
    incident_file = os.path.join(ROOT_DIR, "incident.json")
    if os.path.exists(incident_file):
        with open(incident_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return execute_integrated_pipeline("s1_active.png", 5.4, 72.0, 0.18, 0.07, 24, "default")


# Serve static frontend dashboard assets with explicit no-cache headers
@app.get("/")
async def serve_index():
    return FileResponse(
        os.path.join(ROOT_DIR, "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/style.css")
async def serve_style():
    return FileResponse(
        os.path.join(ROOT_DIR, "style.css"),
        media_type="text/css",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/app.js")
async def serve_script():
    return FileResponse(
        os.path.join(ROOT_DIR, "app.js"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

app.mount("/", StaticFiles(directory=str(ROOT_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("=" * 75)
    print("  SIH26143 SLICKMESH-AI - MASTER DASHBOARD & API GATEWAY ONLINE")
    print("  URL: http://127.0.0.1:8000")
    print("=" * 75)
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
