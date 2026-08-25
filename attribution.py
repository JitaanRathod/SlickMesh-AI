import json
import argparse

def calculate_attribution(candidates_file, output_file, spill_id="SPILL-001"):
    with open(candidates_file, "r") as f:
        data = json.load(f)
        
    ranked_vessels = []
    
    for cand in data["candidates"]:
        evidence = cand["evidence"]
        
        # 1. Distance score (max weight 30)
        # Closer than 2 NM gets full score, scale down to 0 at 15 NM
        dist = evidence["min_distance_nm"]
        if dist <= 2.0:
            dist_score = 30
        elif dist >= 15.0:
            dist_score = 0
        else:
            dist_score = 30 * (1.0 - (dist - 2.0) / 13.0)
            
        # 2. Time consistency score (max weight 25)
        # Closer in time to backtrack estimated window gets higher score
        time_delta = evidence["hours_since_passage"]
        if time_delta <= 1.0:
            time_score = 25
        elif time_delta >= 12.0:
            time_score = 0
        else:
            time_score = 25 * (1.0 - (time_delta - 1.0) / 11.0)
            
        # 3. Speed / SOG consistency (max weight 15)
        # Slicks are often discharged when vessels are traveling slowly or doing bilge washing
        sog = evidence["sog_at_closest_knots"]
        if 1.0 <= sog <= 4.0:
            speed_score = 15
        elif sog < 1.0:
            speed_score = 5
        else:
            # high speed, lower probability of deliberate discharge but still possible
            speed_score = 5 * max(0.0, 1.0 - (sog - 4.0) / 16.0)
            
        # 4. Heading delta (max weight 10)
        # Heading aligned with slick axis/wind direction
        h_delta = evidence["heading_delta_deg"]
        heading_score = 10 * (1.0 - h_delta / 90.0) if h_delta <= 90 else 0
        
        # 5. Vessel type multiplier (max weight 10)
        vtype = cand["vessel_type"].lower()
        if "tanker" in vtype:
            vtype_score = 10
        elif "cargo" in vtype:
            vtype_score = 6
        else:
            vtype_score = 3
            
        # 6. Source region intersection bonus (max weight 10)
        intersect_score = 10 if evidence["intersects_source_region"] else 0
        
        # Total raw score = dist_score + time_score + speed_score + heading_score + vtype_score + intersect_score
        total_score = dist_score + time_score + speed_score + heading_score + vtype_score + intersect_score
        confidence = int(min(max(total_score, 0), 100))
        
        # Generate clear plain-English reasoning
        reasons = []
        if evidence["intersects_source_region"]:
            reasons.append("directly intersected the backtracked source corridor")
        else:
            reasons.append(f"passed within {dist:.1f} NM of the backtracked source corridor")
            
        if time_delta < 4.0:
            reasons.append(f"approximately {time_delta:.1f} hours from suspected release time")
        
        if evidence["sog_at_closest_knots"] < 3.0:
            reasons.append(f"exhibited suspicious low speed ({sog:.1f} knots) suggestive of bilge discharge")
            
        reason_str = f"Vessel {cand['name']} ({cand['vessel_type']}) " + ", and ".join(reasons) + "."
        
        ranked_vessels.append({
            "mmsi": cand["mmsi"],
            "name": cand["name"],
            "vessel_type": cand["vessel_type"],
            "confidence": confidence,
            "reason": reason_str,
            "sub_scores": {
                "distance": round(dist_score / 30.0, 2),
                "time_consistency": round(time_score / 25.0, 2),
                "speed": round(speed_score / 15.0, 2),
                "heading": round(heading_score / 10.0, 2),
                "vessel_type": round(vtype_score / 10.0, 2),
                "environmental_consistency": round(intersect_score / 10.0, 2),
                "track_continuity": 1.0 if evidence["track_continuity"] == "continuous" else 0.5
            }
        })
        
    # Sort descending by confidence
    ranked_vessels.sort(key=lambda x: x["confidence"], reverse=True)
    
    result = {
        "spill_id": spill_id,
        "ranked_vessels": ranked_vessels
    }
    
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
        
    print(f"Phase 3 finished. Output saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3: Multi-criteria vessel attribution engine")
    parser.add_argument("--candidates-json", type=str, default="contract_c_output.json", help="Candidates Contract C from Phase 2")
    parser.add_argument("--output", type=str, default="contract_d_output.json", help="Output JSON path")
    parser.add_argument("--spill-id", type=str, default="SPILL-001", help="Spill Identification Code")
    parser.add_argument("--mock", action="store_true", help="Output mock Contract D directly")
    
    args = parser.parse_args()
    
    if args.mock:
        result = {
            "spill_id": "SPILL-001",
            "ranked_vessels": [
                {
                    "mmsi": "419001234",
                    "name": "MV Ocean Star",
                    "vessel_type": "Tanker",
                    "confidence": 79,
                    "reason": "Passed within 3.2 nm of the backtracked source region 5 hours before detection.",
                    "sub_scores": {
                        "environmental_consistency": 0.9,
                        "distance": 0.85,
                        "time_consistency": 0.7,
                        "track_continuity": 0.8,
                        "heading": 0.75,
                        "speed": 0.6,
                        "vessel_type": 1.0
                    }
                }
            ]
        }
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Mock contract saved to {args.output}")
    else:
        calculate_attribution(args.candidates_json, args.output, args.spill_id)
