import os
import json
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="SIH26143 Oil-Spill Pipeline Integration Server")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schema for running the pipeline
class PipelineRequest(BaseModel):
    image_name: str = "s1_active.png"
    wind_speed: float = 5.4
    wind_direction: float = 72.0
    current_u: float = 0.18
    current_v: float = 0.07
    backtrack_hours: int = 24

@app.post("/api/run-pipeline")
async def run_pipeline(req: PipelineRequest):
    try:
        # Paths
        p1_script = os.path.join("phase1-satellite", "satellite_detect.py")
        p2_script = os.path.join("phase2-ais-gis", "backtrack.py")
        p3_script = os.path.join("phase3-attribution", "attribution.py")
        
        a_out = "contract_a_output.json"
        c_out = "contract_c_output.json"
        d_out = "contract_d_output.json"
        
        # 1. Run Satellite Detection
        p1_cmd = ["python", p1_script, "--image", req.image_name, "--output", a_out]
        subprocess.run(p1_cmd, check=True)
        
        # Load Phase 1 output
        with open(a_out, "r") as f:
            spill_data = json.load(f)
            
        # 2. Run Drift Backtracking & Vessel filtering
        p2_cmd = [
            "python", p2_script,
            "--spill-json", a_out,
            "--current-u", str(req.current_u),
            "--current-v", str(req.current_v),
            "--wind-speed", str(req.wind_speed),
            "--wind-dir", str(req.wind_direction),
            "--backtrack-hours", str(req.backtrack_hours),
            "--ais-db", os.path.join("phase2-ais-gis", "mock_ais_db.json"),
            "--output", c_out
        ]
        subprocess.run(p2_cmd, check=True)
        
        # Load Phase 2 output
        with open(c_out, "r") as f:
            backtrack_data = json.load(f)
            
        # 3. Run Attribution Engine
        p3_cmd = [
            "python", p3_script,
            "--candidates-json", c_out,
            "--spill-id", spill_data["spill_id"],
            "--output", d_out
        ]
        subprocess.run(p3_cmd, check=True)
        
        # Load Phase 3 output
        with open(d_out, "r") as f:
            attribution_data = json.load(f)
            
        # 4. Integrate into Contract E
        # Convert vessels coordinates to [lon, lat] for Leaflet / Contract E standard
        vessels_e = []
        # Create map from MMSI to candidate for track information
        candidates_map = {c["mmsi"]: c for c in backtrack_data["candidates"]}
        
        for v in attribution_data["ranked_vessels"]:
            cand = candidates_map.get(v["mmsi"])
            if cand:
                # convert lat/lons from [lat, lon] to [lon, lat] for GeoJSON standard in Contract E
                pos_lon_lat = [cand["position"]["longitude"], cand["position"]["latitude"]]
                track_lon_lat = [[pt[1], pt[0]] for pt in cand["track"]]
                
                vessels_e.append({
                    "name": v["name"],
                    "mmsi": v["mmsi"],
                    "type": v["vessel_type"],
                    "confidence": v["confidence"],
                    "reason": v["reason"],
                    "position": pos_lon_lat,
                    "track": track_lon_lat,
                    "sub_scores": v["sub_scores"]
                })
        
        merged_e = {
            "incident": {
                "id": spill_data["spill_id"],
                "detected_at": spill_data["detected_at"],
                "area_km2": spill_data["area_km2"],
                "confidence": spill_data["confidence"],
                "polygon": spill_data["polygon"]
            },
            "environment": {
                "current_u_ms": req.current_u,
                "current_v_ms": req.current_v,
                "wind_speed_ms": req.wind_speed,
                "wind_direction_deg": req.wind_direction,
                "source_model": "Copernicus Marine / INCOIS"
            },
            "source_region": backtrack_data["source_region"],
            "vessels": vessels_e
        }
        
        # Write back to static folder for UI loading
        static_json_path = os.path.join("phase4-dashboard", "incident.json")
        os.makedirs(os.path.dirname(static_json_path), exist_ok=True)
        with open(static_json_path, "w") as f:
            json.dump(merged_e, f, indent=2)
            
        return merged_e
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Fallback endpoint returning mock incident
@app.get("/api/mock-incident")
async def get_mock_incident():
    mock_path = os.path.join("phase4-dashboard", "incident.json")
    if os.path.exists(mock_path):
        with open(mock_path, "r") as f:
            return json.load(f)
    else:
        # Default mock fallback
        return {
            "incident": {
                "id": "SPILL-001", "detected_at": "2026-08-25T06:00:00Z",
                "area_km2": 3.2, "confidence": 0.87,
                "polygon": [[67.15,20.45],[67.45,20.75],[67.90,20.62],[67.70,20.30],[67.35,20.25]]
            },
            "environment": {
                "current_u_ms": 0.18, "current_v_ms": 0.07, "wind_speed_ms": 5.4,
                "wind_direction_deg": 72, "source_model": "Copernicus Marine"
            },
            "source_region": { "latitude": 20.48, "longitude": 67.52, "radius_km": 22, "backtrack_hours": 24 },
            "vessels": [
                {
                    "name": "MV Ocean Star", "mmsi": "419001234", "type": "Tanker", "confidence": 86,
                    "reason": "Passed near the backtracked source region",
                    "position": [67.10, 20.15],
                    "track": [[67.10,20.15],[66.90,20.00],[66.70,19.85]]
                }
            ]
        }

# Serve frontend dashboard assets
app.mount("/", StaticFiles(directory="phase4-dashboard", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Make sure static dashboard directory exists
    os.makedirs("phase4-dashboard", exist_ok=True)
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
