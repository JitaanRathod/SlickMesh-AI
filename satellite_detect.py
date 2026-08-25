import json
import os
import argparse
import random
from datetime import datetime

def detect_spill(image_path: str) -> dict:
    """
    Simulates a U-Net satellite oil-spill detection pipeline on a Sentinel-1 image.
    Generates a detection polygon, centroid, area, confidence, and quality flag.
    """
    # Deterministic output based on the image name to keep it consistent
    img_name = os.path.basename(image_path).lower()
    
    # We will generate mock spill detections depending on which mock image is processed
    if "spill" in img_name or "sentinel" in img_name or img_name == "s1_active.png":
        # Arabian Sea mock coordinates near Mumbai offshore (Mumbai High)
        polygon = [
            [72.35, 19.65],
            [72.38, 19.68],
            [72.42, 19.66],
            [72.40, 19.62],
            [72.36, 19.63]
        ]
        centroid = {"lat": 19.648, "lon": 72.382}
        area_km2 = round(4.8 + random.uniform(-0.5, 0.5), 2)
        confidence = round(0.89 + random.uniform(-0.02, 0.03), 2)
        quality_flag = "favorable"
        notes = "Clear dark anomaly detected in Sentinel-1 SAR VV polarization; favorable wind speed (5.2 m/s)."
    elif "bay_of_bengal" in img_name:
        # Bay of Bengal mock coordinates near Krishna-Godavari Basin
        polygon = [
            [82.25, 16.15],
            [82.28, 16.18],
            [82.32, 16.16],
            [82.30, 16.12],
            [82.26, 16.13]
        ]
        centroid = {"lat": 16.148, "lon": 82.282}
        area_km2 = round(6.1 + random.uniform(-0.3, 0.3), 2)
        confidence = round(0.92 + random.uniform(-0.01, 0.02), 2)
        quality_flag = "favorable"
        notes = "Distinct linear anomaly matching slick pattern; low-wind risk."
    else:
        # Default mock spill (Contract A sample values)
        polygon = [
            [67.15, 20.45],
            [67.45, 20.75],
            [67.90, 20.62],
            [67.70, 20.30],
            [67.35, 20.25]
        ]
        centroid = {"lat": 20.48, "lon": 67.52}
        area_km2 = 3.2
        confidence = 0.87
        quality_flag = "favorable"
        notes = "Candidate detection — not chemically confirmed."

    return {
        "spill_id": f"SPILL-{random.randint(100, 999)}",
        "detected_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "spill_detected": True,
        "confidence": confidence,
        "area_km2": area_km2,
        "centroid": centroid,
        "polygon": polygon,
        "quality_flag": quality_flag,
        "notes": notes
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 1: Satellite SAR spill detection U-Net simulation")
    parser.add_argument("--image", type=str, default="s1_active.png", help="Path to Sentinel-1 SAR image file")
    parser.add_argument("--output", type=str, default="contract_a_output.json", help="Output path for JSON contract")
    parser.add_argument("--mock", action="store_true", help="Proactively output the exact contract mock sample")
    
    args = parser.parse_args()
    
    if args.mock:
        result = {
            "spill_id": "SPILL-001",
            "detected_at": "2026-08-25T06:00:00Z",
            "spill_detected": True,
            "confidence": 0.87,
            "area_km2": 3.2,
            "centroid": { "lat": 20.48, "lon": 67.52 },
            "polygon": [
                [67.15, 20.45],
                [67.45, 20.75],
                [67.90, 20.62],
                [67.70, 20.30],
                [67.35, 20.25]
            ],
            "quality_flag": "favorable",
            "notes": "candidate detection — not chemically confirmed"
        }
    else:
        result = detect_spill(args.image)
        
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
        
    print(f"Phase 1 finished. Detection saved to {args.output}")
