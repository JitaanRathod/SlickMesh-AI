import json
import math
import argparse
from datetime import datetime, timedelta

def haversine(lat1, lon1, lat2, lon2):
    # Returns distance in nautical miles
    R = 6371000  # radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_meters = R * c
    return distance_meters / 1852.0  # meters to nautical miles

def parse_time(ts):
    return datetime.strptime(ts.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")

def format_time(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def run_backtrack(spill_file, env_data, backtrack_hours, output_file, ais_db_file):
    # Load spill data
    with open(spill_file, "r") as f:
        spill = json.load(f)
    
    centroid = spill["centroid"]
    detected_at = parse_time(spill["detected_at"])
    
    # Extract weather/current conditions
    current_u = env_data["current_u_ms"]
    current_v = env_data["current_v_ms"]
    wind_speed = env_data["wind_speed_ms"]
    wind_dir = env_data["wind_direction_deg"]
    
    # Calculate drift velocity vector (m/s)
    # Wind direction is coming FROM, so blowing TO is direction + 180
    wind_to_rad = math.radians((wind_dir + 180) % 360)
    wind_u = wind_speed * math.sin(wind_to_rad)
    wind_v = wind_speed * math.cos(wind_to_rad)
    
    # Net drift = current + 3% of wind
    drift_u = current_u + 0.03 * wind_u
    drift_v = current_v + 0.03 * wind_v
    
    # Backtrack displacements (meters)
    disp_u_meters = drift_u * (backtrack_hours * 3600)
    disp_v_meters = drift_v * (backtrack_hours * 3600)
    
    # Reversing displacement for backtrack origin
    rev_u_meters = -disp_u_meters
    rev_v_meters = -disp_v_meters
    
    # Degrees conversion
    lat_deg_per_m = 1.0 / 111320.0
    lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(centroid["lat"])))
    
    origin_lat = centroid["lat"] + rev_v_meters * lat_deg_per_m
    origin_lon = centroid["lon"] + rev_u_meters * lon_deg_per_m
    
    # Calculate backtracking source radius (increases with backtrack time and wind uncertainty)
    radius_km = round(10.0 + (0.5 * wind_speed * backtrack_hours) / 10.0, 1)
    
    source_region = {
        "latitude": round(origin_lat, 4),
        "longitude": round(origin_lon, 4),
        "radius_km": radius_km,
        "backtrack_hours": backtrack_hours
    }
    
    # Load AIS database
    with open(ais_db_file, "r") as f:
        vessels = json.load(f)
        
    candidates = []
    estimated_spill_origin_time = detected_at - timedelta(hours=backtrack_hours)
    
    for vessel in vessels:
        min_dist_nm = float('inf')
        closest_point = None
        closest_vessel_time = None
        
        # Check track points for proximity
        for pt in vessel["track"]:
            pt_time = parse_time(pt["timestamp"])
            dist_nm = haversine(origin_lat, origin_lon, pt["lat"], pt["lon"])
            if dist_nm < min_dist_nm:
                min_dist_nm = dist_nm
                closest_point = pt
                closest_vessel_time = pt_time
                
        if closest_point is not None:
            # Check spatial intersection
            intersects = (min_dist_nm * 1.852) <= radius_km
            
            # Check temporal delta
            time_diff_hours = abs((closest_vessel_time - estimated_spill_origin_time).total_seconds()) / 3600.0
            
            # Heading delta (assumed path direction vs backtrack origin direction)
            # Simulating evidence parameters
            heading_delta = abs(closest_point["heading"] - wind_dir) % 180
            if heading_delta > 90:
                heading_delta = 180 - heading_delta
                
            track_lat_lons = [[pt["lat"], pt["lon"]] for pt in vessel["track"]]
            
            candidates.append({
                "mmsi": vessel["mmsi"],
                "imo": vessel["imo"],
                "name": vessel["name"],
                "vessel_type": vessel["vessel_type"],
                "position": {"latitude": closest_point["lat"], "longitude": closest_point["lon"]},
                "track": track_lat_lons,
                "evidence": {
                    "min_distance_nm": round(min_dist_nm, 2),
                    "hours_since_passage": round(time_diff_hours, 1),
                    "heading_delta_deg": int(heading_delta),
                    "sog_at_closest_knots": closest_point["sog"],
                    "intersects_source_region": intersects,
                    "track_continuity": "continuous" if len(vessel["track"]) > 3 else "sporadic"
                }
            })
            
    # Save output (Contract C format)
    result = {
        "source_region": source_region,
        "candidates": candidates
    }
    
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
        
    print(f"Phase 2 finished. Output saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2: AIS & Reverse-drift backtracking")
    parser.add_argument("--spill-json", type=str, default="contract_a_output.json", help="Input Spill Contract A")
    parser.add_argument("--current-u", type=float, default=0.18, help="Eastward current velocity in m/s")
    parser.add_argument("--current-v", type=float, default=0.07, help="Northward current velocity in m/s")
    parser.add_argument("--wind-speed", type=float, default=5.4, help="Wind speed in m/s")
    parser.add_argument("--wind-dir", type=float, default=72.0, help="Wind direction in degrees (0-360, wind from)")
    parser.add_argument("--backtrack-hours", type=int, default=24, help="Number of hours to backtrack")
    parser.add_argument("--ais-db", type=str, default="mock_ais_db.json", help="Path to mock AIS DB")
    parser.add_argument("--output", type=str, default="contract_c_output.json", help="Output JSON path")
    parser.add_argument("--mock", action="store_true", help="Output mock JSON contract directly")
    
    args = parser.parse_args()
    
    if args.mock:
        result = {
            "source_region": {
                "latitude": 20.48,
                "longitude": 67.52,
                "radius_km": 22,
                "backtrack_hours": 24
            },
            "candidates": [
                {
                    "mmsi": "419001234",
                    "imo": "9123456",
                    "name": "MV Ocean Star",
                    "vessel_type": "Tanker",
                    "position": { "latitude": 20.15, "longitude": 67.10 },
                    "track": [
                        [19.70, 66.40],
                        [19.85, 66.70],
                        [20.00, 66.90],
                        [20.15, 67.10]
                    ],
                    "evidence": {
                        "min_distance_nm": 3.2,
                        "hours_since_passage": 5.1,
                        "heading_delta_deg": 12,
                        "sog_at_closest_knots": 1.4,
                        "intersects_source_region": true,
                        "track_continuity": "continuous"
                    }
                }
            ]
        }
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Mock contract saved to {args.output}")
    else:
        env = {
            "current_u_ms": args.current_u,
            "current_v_ms": args.current_v,
            "wind_speed_ms": args.wind_speed,
            "wind_direction_deg": args.wind_dir
        }
        run_backtrack(args.spill_json, env, args.backtrack_hours, args.output, args.ais_db)
