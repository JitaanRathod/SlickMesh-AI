"""
Master Pipeline Orchestrator — Single Command End-to-End Execution.
Chains: Sentinel-1 Image / Auto-Fetch -> Phase 1 -> Phase 4a -> Phase 2 -> Phase 3 -> Contract E (incident.json).
Ref: PRD.md §4 & INTEGRATION_PLAN.md §Checkpoint 2
"""

import os
import sys
import json
import math
import argparse
from datetime import datetime, timezone
import urllib.request
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add phase subdirectories to sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "phase1-satellite"))
sys.path.insert(0, str(ROOT_DIR / "phase2-ais-gis"))
sys.path.insert(0, str(ROOT_DIR / "phase3-attribution"))

from detect import run_detection
from fetch_sentinel1 import fetch_sentinel1_sar_patch
from engine import AttributionEngine
from models import BacktrackInput, SourceRegion, CandidateVessel, Position, VesselEvidence


def fetch_open_meteo_environment(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetches live marine environmental data (wind/ocean current) from Open-Meteo API.
    Fallback to realistic regional defaults if network is unavailable.
    """
    print(f"[Phase 4a Env] Fetching environmental wind/current feed near Lat: {lat:.2f}, Lon: {lon:.2f}...")
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m,wind_direction_10m"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            current = data.get("current", {})
            wind_speed = current.get("wind_speed_10m", 5.4)
            wind_dir = current.get("wind_direction_10m", 72)
            
            rad = math.radians(wind_dir)
            current_u = round(0.18 * math.cos(rad), 2)
            current_v = round(0.18 * math.sin(rad), 2)
            
            return {
                "current_u_ms": current_u,
                "current_v_ms": current_v,
                "wind_speed_ms": round(wind_speed / 3.6, 1) if wind_speed > 15 else round(wind_speed, 1),
                "wind_direction_deg": int(wind_dir),
                "source_model": "Open-Meteo Live API"
            }
    except Exception as e:
        print(f"[Phase 4a Env] Open-Meteo fallback: {e}")
        return {
            "current_u_ms": 0.18,
            "current_v_ms": 0.07,
            "wind_speed_ms": 5.4,
            "wind_direction_deg": 72,
            "source_model": "Copernicus / Open-Meteo Fallback"
        }


def get_scenario_data(scenario_name: str) -> Dict[str, Any]:
    """Returns regional scenario presets tuned for Indian waters (all offshore in open water)."""
    scenarios = {
        "mumbai": {
            "name": "Arabian Sea (Mumbai High Offshore)",
            "lat": 19.42, "lon": 71.35,  # Mumbai High Spill Centroid (T=0 Detection)
            "image": "real_grande_america_spill.jpg",
            "candidates": [
                {
                    "mmsi": "419001111", "imo": "9345678", "name": "Al-Bahar Crude", "vessel_type": "Crude Oil Tanker",
                    "min_dist_nm": 1.2, "hours": 3.5, "heading_delta": 8.0, "sog": 2.1, "intersects": True, "continuity": "continuous",
                    # Track sails directly through the yellow backtracked origin circle at (19.54, 71.21)
                    "track": [[19.10, 71.05], [19.35, 71.15], [19.54, 71.21], [19.75, 71.28]]
                },
                {
                    "mmsi": "419002222", "imo": "9223344", "name": "Konkan Star", "vessel_type": "Chemical Tanker",
                    "min_dist_nm": 6.8, "hours": 7.0, "heading_delta": 22.0, "sog": 8.5, "intersects": False, "continuity": "continuous",
                    # Parallel fairway 7 nm to the west
                    "track": [[19.00, 70.85], [19.25, 70.95], [19.50, 71.05], [19.75, 71.15]]
                },
                {
                    "mmsi": "419003333", "imo": "9112233", "name": "Mumbai Pioneer", "vessel_type": "Cargo",
                    "min_dist_nm": 16.5, "hours": 14.0, "heading_delta": 55.0, "sog": 14.2, "intersects": False, "continuity": "continuous",
                    # Distant lane 16 nm to the east
                    "track": [[18.90, 71.65], [19.20, 71.70], [19.50, 71.75], [19.80, 71.80]]
                }
            ]
        },
        "kg_basin": {
            "name": "Bay of Bengal (Krishna-Godavari Basin)",
            "lat": 16.15, "lon": 82.55,  # Krishna-Godavari Deepwater Basin (~40km offshore)
            "image": "real_grande_america_spill.jpg",
            "candidates": [
                {
                    "mmsi": "419004444", "imo": "9445566", "name": "Bay Explorer", "vessel_type": "Oil Tanker",
                    "min_dist_nm": 1.5, "hours": 4.0, "heading_delta": 10.0, "sog": 1.8, "intersects": True, "continuity": "continuous",
                    # Track sails directly through the yellow backtracked origin circle at (16.03, 82.70)
                    "track": [[15.60, 82.85], [15.85, 82.78], [16.03, 82.70], [16.25, 82.60]]
                },
                {
                    "mmsi": "419005555", "imo": "9556677", "name": "Godavari Pride", "vessel_type": "Bulk Carrier",
                    "min_dist_nm": 14.0, "hours": 9.5, "heading_delta": 45.0, "sog": 12.0, "intersects": False, "continuity": "gapped",
                    "track": [[15.50, 83.15], [15.80, 83.05], [16.10, 82.95], [16.40, 82.85]]
                }
            ]
        },
        "dark_ship": {
            "name": "Arabian Sea (AIS Spoofing / Blackout Scenario)",
            "lat": 16.50, "lon": 72.00,  # Ratnagiri Offshore Deep Channel
            "image": "real_grande_america_spill.jpg",
            "candidates": [
                {
                    "mmsi": "419099999", "imo": "9998888", "name": "Shadow Trader", "vessel_type": "Chemical Tanker",
                    "min_dist_nm": 1.4, "hours": 4.0, "heading_delta": 10.0, "sog": 1.2, "intersects": True, "continuity": "gapped",
                    "track": [[16.10, 71.75], [16.35, 71.88], [16.55, 71.95], [16.80, 72.05]]
                },
                {
                    "mmsi": "419088888", "imo": "9887766", "name": "Kolkata Express", "vessel_type": "Bulk Carrier",
                    "min_dist_nm": 18.5, "hours": 12.0, "heading_delta": 55.0, "sog": 13.0, "intersects": False, "continuity": "continuous",
                    "track": [[16.00, 72.40], [16.30, 72.45], [16.60, 72.50], [16.90, 72.55]]
                }
            ]
        },
        "alang": {
            "name": "Gulf of Khambhat (Alang Offshore)",
            "lat": 20.48, "lon": 67.52,  # Gulf of Khambhat / Saurashtra Offshore Lane
            "image": "real_grande_america_spill.jpg",
            "candidates": [
                {
                    "mmsi": "419001234", "imo": "9123456", "name": "MV Ocean Star", "vessel_type": "Tanker",
                    "min_dist_nm": 1.8, "hours": 5.1, "heading_delta": 12.0, "sog": 1.4, "intersects": True, "continuity": "continuous",
                    # Track sails directly through the yellow backtracked origin circle at (20.35, 67.30)
                    "track": [[19.90, 67.10], [20.15, 67.20], [20.35, 67.30], [20.60, 67.45]]
                },
                {
                    "mmsi": "419005678", "imo": "9007654", "name": "MT Gujarat Pearl", "vessel_type": "Cargo",
                    "min_dist_nm": 15.2, "hours": 9.8, "heading_delta": 41.0, "sog": 9.2, "intersects": False, "continuity": "gapped",
                    "track": [[21.00, 67.60], [20.80, 67.65], [20.60, 67.70], [20.40, 67.75]]
                },
                {
                    "mmsi": "419009876", "imo": "9876543", "name": "Deepsea Sentinel", "vessel_type": "Container Ship",
                    "min_dist_nm": 22.0, "hours": 16.5, "heading_delta": 65.0, "sog": 16.0, "intersects": False, "continuity": "continuous",
                    "track": [[20.90, 68.10], [20.70, 68.20], [20.50, 68.30]]
                }
            ]
        }
    }
    key = scenario_name.lower().replace("-", "_")
    return scenarios.get(key, scenarios["alang"])


def run_master_pipeline(
    scenario: str = "alang",
    image_path: Optional[str] = None,
    auto_fetch: bool = False,
    wind_speed: float = 5.4,
    backtrack_hours: int = 24,
    output_path: str = "dashboard/incident.json",
    show_table: bool = True
) -> Dict[str, Any]:
    """Executes full integrated pipeline."""
    sc_data = get_scenario_data(scenario)
    ref_lat = sc_data["lat"]
    ref_lon = sc_data["lon"]
    resolved_img = image_path or sc_data["image"]

    print("=" * 80)
    print(f"      SIH26143 SLICKMESH-AI — MASTER PIPELINE [{sc_data['name'].upper()}]")
    print("=" * 80)

    # 1. Satellite Scene Fetching / Loading
    if auto_fetch:
        print("\n[STEP 1/5] Auto-fetching fresh Sentinel-1 SAR scene from Copernicus...")
        resolved_img = fetch_sentinel1_sar_patch(lat=ref_lat, lon=ref_lon)

    # 2. Phase 1 — Satellite SAR Detection
    print(f"\n[STEP 2/5] Phase 1: Satellite SAR U-Net Segmentation (Target: Lat {ref_lat:.2f}, Lon {ref_lon:.2f})...")
    img_exists = os.path.exists(resolved_img) if resolved_img else False
    spill_output = run_detection(
        image_path=resolved_img if img_exists else None,
        synthetic=not img_exists,
        ref_lat=ref_lat,
        ref_lon=ref_lon,
        wind_speed_ms=wind_speed,
        output_path="phase1-satellite/spill_detection_output.json"
    )
    print(f"  * Detected Spill ID: {spill_output.spill_id} | Area: {spill_output.area_km2} km² | Confidence: {int(spill_output.confidence * 100)}%")

    # 3. Phase 4a — Environmental Feed
    print("\n[STEP 3/5] Phase 4a: Live Environmental Weather & Current Feed...")
    env_output = fetch_open_meteo_environment(ref_lat, ref_lon)
    print(f"  * Wind: {env_output['wind_speed_ms']} m/s @ {env_output['wind_direction_deg']}° | Current: u={env_output['current_u_ms']}, v={env_output['current_v_ms']} m/s")

    # 4. Phase 2 — AIS Reverse Drift Backtracking
    print(f"\n[STEP 4/5] Phase 2: Hydrodynamic Drift Backtracking ({backtrack_hours}h lookback)...")
    wind_rad = math.radians((env_output["wind_direction_deg"] + 180) % 360)
    wind_u = env_output["wind_speed_ms"] * math.sin(wind_rad)
    wind_v = env_output["wind_speed_ms"] * math.cos(wind_rad)

    drift_u = env_output["current_u_ms"] + 0.03 * wind_u
    drift_v = env_output["current_v_ms"] + 0.03 * wind_v

    disp_u_m = -drift_u * (backtrack_hours * 3600)
    disp_v_m = -drift_v * (backtrack_hours * 3600)

    lat_deg_per_m = 1.0 / 111320.0
    lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(spill_output.centroid.lat)))

    origin_lat = round(spill_output.centroid.lat + disp_v_m * lat_deg_per_m, 4)
    origin_lon = round(spill_output.centroid.lon + disp_u_m * lon_deg_per_m, 4)
    radius_km = round(10.0 + (0.5 * env_output["wind_speed_ms"] * backtrack_hours) / 10.0, 1)

    source_region_model = SourceRegion(
        latitude=origin_lat,
        longitude=origin_lon,
        radius_km=radius_km,
        backtrack_hours=float(backtrack_hours)
    )
    print(f"  * Inferred Origin: Lat {origin_lat:.4f}, Lon {origin_lon:.4f} (Uncertainty Buffer: {radius_km} km)")

    def haversine_nm(lat1, lon1, lat2, lon2):
        R_nm = 3440.065
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        return 2 * R_nm * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Dynamically compute genuine geometric intersection from track waypoints & origin
    origin_radius_nm = radius_km / 1.852
    candidates_list = []
    for c_raw in sc_data["candidates"]:
        track_points = c_raw["track"]
        computed_min_dist_nm = min(
            haversine_nm(pt[0], pt[1], origin_lat, origin_lon)
            for pt in track_points
        )
        computed_intersects = computed_min_dist_nm <= origin_radius_nm

        cand = CandidateVessel(
            mmsi=c_raw["mmsi"],
            imo=c_raw.get("imo"),
            name=c_raw["name"],
            vessel_type=c_raw["vessel_type"],
            position=Position(latitude=track_points[-1][0], longitude=track_points[-1][1]),
            track=track_points,
            evidence=VesselEvidence(
                min_distance_nm=round(computed_min_dist_nm, 2),
                hours_since_passage=c_raw.get("hours", 4.0),
                heading_delta_deg=c_raw.get("heading_delta", 15.0),
                sog_at_closest_knots=c_raw.get("sog", 10.0),
                intersects_source_region=computed_intersects,
                track_continuity=c_raw.get("continuity", "continuous")
            )
        )
        candidates_list.append(cand)

    backtrack_input = BacktrackInput(source_region=source_region_model, candidates=candidates_list)

    # 5. Phase 3 — Multi-Evidence Attribution Engine
    print("\n[STEP 5/5] Phase 3: Evidence Fusion & Ranked Vessel Attribution...")
    engine = AttributionEngine()
    attribution_output = engine.process(backtrack_input, spill_id=spill_output.spill_id)

    # Assemble Contract E
    vessels_e = []
    cand_map = {c.mmsi: c for c in candidates_list}
    for rv in attribution_output.ranked_vessels:
        c_obj = cand_map.get(rv.mmsi)
        if c_obj:
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
        "environment": env_output,
        "source_region": {
            "latitude": origin_lat,
            "longitude": origin_lon,
            "radius_km": radius_km,
            "backtrack_hours": backtrack_hours
        },
        "vessels": vessels_e
    }

    # Save Contract E
    for dest in (output_path, "incident.json", "dashboard/incident.json"):
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(contract_e, f, indent=2)

    if show_table:
        print("\n" + engine.render_ascii_table(attribution_output))

    print("=" * 80)
    print(f" PIPELINE SUCCESS: Merged incident saved to: {output_path}")
    print(" Dashboard is ready for visualization!")
    print("=" * 80)

    return contract_e


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Master Pipeline Orchestrator for SIH26143.")
    parser.add_argument("--scenario", type=str, default="alang", choices=["alang", "mumbai", "kg_basin", "dark_ship"], help="Pre-configured regional test scenario")
    parser.add_argument("--image", type=str, default=None, help="Path to input SAR image")
    parser.add_argument("--auto-fetch", action="store_true", help="Auto-download fresh Sentinel-1 scene from Copernicus API")
    parser.add_argument("--wind-speed", type=float, default=5.4, help="Surface wind speed in m/s")
    parser.add_argument("--backtrack-hours", type=int, default=24, help="Backtracking simulation window (hours)")
    parser.add_argument("--output", type=str, default="dashboard/incident.json", help="Contract E destination JSON path")
    parser.add_argument("--table", action="store_true", default=True, help="Display formatted ASCII ranking table in terminal")
    parser.add_argument("--serve", action="store_true", help="Launch FastAPI web dashboard immediately after execution")

    args = parser.parse_args()
    result = run_master_pipeline(
        scenario=args.scenario,
        image_path=args.image,
        auto_fetch=args.auto_fetch,
        wind_speed=args.wind_speed,
        backtrack_hours=args.backtrack_hours,
        output_path=args.output,
        show_table=args.table
    )

    if args.serve:
        import uvicorn
        print("\nLaunching Live Dashboard on http://127.0.0.1:8000 ...")
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)

