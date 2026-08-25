"""
Main Phase 1 CLI Detection Pipeline Script.
Inference, Geometry Extraction, Wind Quality Flagging & Contract A JSON Validation.
Ref: API_CONTRACTS.md §A and phase1-satellite-detection.md §7
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
import torch
import numpy as np
from PIL import Image

# Ensure script directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contracts import SatelliteDetectionOutput, get_mock_contract_a
from geometry import extract_slick_geometry
from wind_flag import evaluate_wind_quality_flag
from model import UNet
from dataset import generate_synthetic_sar_patch


def run_detection(
    image_path: str = None,
    synthetic: bool = False,
    weights_path: str = "weights/unet_best.pth",
    wind_speed_ms: float = 5.4,
    spill_id: str = "SPILL-001",
    ref_lat: float = 20.48,
    ref_lon: float = 67.52,
    output_path: str = "spill_detection_output.json",
    mock: bool = False
) -> SatelliteDetectionOutput:
    """
    Executes Phase 1 satellite slick detection pipeline.
    """
    if mock:
        print("[Phase 1 Detect] Running in --mock mode. Emitting canonical Contract A output.")
        output_data = get_mock_contract_a()
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # 1. Load image or generate synthetic SAR patch
        if synthetic or image_path is None or not os.path.exists(image_path):
            print("[Phase 1 Detect] Generating synthetic SAR patch for inference...")
            img_tensor, gt_mask_tensor = generate_synthetic_sar_patch(image_size=256, has_spill=True, seed=42)
            img_tensor = img_tensor.unsqueeze(0).to(device)
        else:
            print(f"[Phase 1 Detect] Loading input SAR image: {image_path}")
            raw_img = Image.open(image_path).convert("L").resize((256, 256))
            img_np = np.array(raw_img, dtype=np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np).unsqueeze(0).unsqueeze(0).to(device)

        # 2. Run U-Net model inference
        model = UNet(in_channels=1, out_channels=1).to(device)
        if os.path.exists(weights_path):
            print(f"[Phase 1 Detect] Loading trained model weights from: {weights_path}")
            model.load_state_dict(torch.load(weights_path, map_location=device))
        else:
            print(f"[Phase 1 Detect] Warning: Weights file {weights_path} not found. Running baseline inference.")
        
        model.eval()
        with torch.no_grad():
            prob_map = model(img_tensor).squeeze().cpu().numpy()

        binary_mask = (prob_map > 0.5).astype(np.uint8)

        # 3. Extract geometry stats (area, centroid, polygon)
        geom_stats = extract_slick_geometry(
            mask_np=binary_mask,
            prob_map=prob_map,
            ref_lat=ref_lat,
            ref_lon=ref_lon
        )

        # 4. Evaluate wind quality flag
        quality_flag = evaluate_wind_quality_flag(wind_speed_ms)

        # 5. Assemble Contract A output object
        timestamp_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        output_data = SatelliteDetectionOutput(
            spill_id=spill_id,
            detected_at=timestamp_iso,
            spill_detected=geom_stats["spill_detected"],
            confidence=geom_stats["confidence"],
            area_km2=geom_stats["area_km2"],
            centroid=geom_stats["centroid"],
            polygon=geom_stats["polygon"],
            quality_flag=quality_flag,
            notes="candidate detection — not chemically confirmed"
        )

    # 6. Validate & Write output JSON
    json_payload = output_data.model_dump_json(indent=2)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_payload)

    print(f"[Phase 1 Detect] Detection payload successfully written to: {output_path}")
    return output_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 1 Satellite SAR Oil Slick Detection CLI.")
    parser.add_argument("--image", type=str, default=None, help="Path to input SAR image")
    parser.add_argument("--synthetic", action="store_true", default=False, help="Run detection on synthetic SAR patch")
    parser.add_argument("--weights", type=str, default="weights/unet_best.pth", help="Path to PyTorch model weights")
    parser.add_argument("--wind-speed", type=float, default=5.4, help="Surface wind speed in m/s")
    parser.add_argument("--spill-id", type=str, default="SPILL-001", help="Custom spill ID")
    parser.add_argument("--ref-lat", type=float, default=20.48, help="Reference latitude")
    parser.add_argument("--ref-lon", type=float, default=67.52, help="Reference longitude")
    parser.add_argument("--output", type=str, default="spill_detection_output.json", help="Output JSON path")
    parser.add_argument("--mock", action="store_true", default=False, help="Emit canonical Contract A mock payload")

    args = parser.parse_args()
    run_detection(
        image_path=args.image,
        synthetic=args.synthetic,
        weights_path=args.weights,
        wind_speed_ms=args.wind_speed,
        spill_id=args.spill_id,
        ref_lat=args.ref_lat,
        ref_lon=args.ref_lon,
        output_path=args.output,
        mock=args.mock
    )
