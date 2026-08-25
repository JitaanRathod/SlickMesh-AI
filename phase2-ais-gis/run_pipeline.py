"""
run_pipeline.py — Phase 2 end-to-end pipeline entry point.

Modes:
  --mock   Produce sample Contract C output exactly matching the phase doc example.
           No external data or API calls. Use this to verify the schema is correct
           and to diff your real output's shape against a known-good example.

  (no flag) Full pipeline:
           1. Load cleaned AIS from data/ais_cleaned.parquet (run scripts/download_danish.py first
              for offline dev, or wait for ais_listener.py to accumulate real data)
           2. Build trajectories
           3. Backtrack origin corridor via Open-Meteo
           4. Match candidates + compute evidence
           5. Validate + write output/contract_c.json

Usage:
  cd phase2-ais-gis
  python run_pipeline.py --mock      # known-good sample output (no deps needed)
  python run_pipeline.py             # full pipeline
  python run_pipeline.py --mock-env  # full pipeline but use mock_env.json instead of Open-Meteo
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from src.config import CLEANED_PARQUET, CONTRACT_C_FILE
from src.contract_writer import validate_and_write


# ---------------------------------------------------------------------------
# Mock output (exactly matching the Contract C example in the phase doc)
# ---------------------------------------------------------------------------

MOCK_CONTRACT_C = {
    "source_region": {
        "latitude": 20.48,
        "longitude": 67.52,
        "radius_km": 22,
        "backtrack_hours": 24,
    },
    "candidates": [
        {
            "mmsi": "419001234",
            "imo": "9123456",
            "name": "MV Ocean Star",
            "vessel_type": "Tanker",
            "position": {"latitude": 20.15, "longitude": 67.10},
            "track": [
                [19.70, 66.40],
                [19.85, 66.70],
                [20.00, 66.90],
                [20.15, 67.10],
            ],
            "evidence": {
                "min_distance_nm": 3.2,
                "hours_since_passage": 5.1,
                "heading_delta_deg": 12,
                "sog_at_closest_knots": 1.4,
                "intersects_source_region": True,
                "track_continuity": "continuous",
            },
        }
    ],
}


def run_mock() -> None:
    """Write the phase-doc sample output, validate it, and exit."""
    logger.info("=== MOCK MODE — writing sample Contract C ===")
    payload = validate_and_write(
        source_region=MOCK_CONTRACT_C["source_region"],
        candidates=MOCK_CONTRACT_C["candidates"],
    )
    logger.info("Mock Contract C written to %s", CONTRACT_C_FILE)
    print(json.dumps(payload, indent=2))


def run_full(use_mock_env: bool = False) -> None:
    """Full pipeline — requires cleaned Parquet (data/ais_cleaned.parquet)."""
    from src.trajectory_builder import build_trajectories
    from src.backtracker import compute_origin_corridor
    from src.candidate_matcher import match_candidates

    # --- 1. Load spill (mock until Phase 1 is ready) ---
    spill_path = BASE_DIR / "mock_spill.json"
    with open(spill_path) as f:
        spill = json.load(f)

    spill_lat = spill["centroid"]["lat"]
    spill_lon = spill["centroid"]["lon"]
    detected_at = datetime.fromisoformat(spill["detected_at"].replace("Z", "+00:00"))
    logger.info("Spill: %s  centroid=(%.4f, %.4f)  at=%s", spill["spill_id"], spill_lat, spill_lon, detected_at)

    # --- 2. Check Parquet exists ---
    if not CLEANED_PARQUET.exists():
        logger.error(
            "Cleaned AIS Parquet not found at %s.\n"
            "Run:  python scripts/download_danish.py\n"
            "   or start the listener:  python -m src.ais_listener",
            CLEANED_PARQUET,
        )
        sys.exit(1)

    # --- 3. Build trajectories ---
    logger.info("Building trajectories …")
    tc = build_trajectories()
    logger.info("Trajectory collection: %d segments", len(tc))

    # --- 4. Backtrack origin corridor ---
    logger.info("Computing origin corridor …")
    mock_env_path = BASE_DIR / "mock_env.json" if use_mock_env else None
    corridor = compute_origin_corridor(
        spill_lat=spill_lat,
        spill_lon=spill_lon,
        mock_env_path=mock_env_path,
    )
    logger.info(
        "Origin corridor: lat=%.4f lon=%.4f radius=%.1f km (backtrack %d h)",
        corridor["latitude"],
        corridor["longitude"],
        corridor["radius_km"],
        corridor["backtrack_hours"],
    )

    # --- 5. Match candidates ---
    logger.info("Matching candidates …")
    candidates = match_candidates(
        tc=tc,
        spill_lat=spill_lat,
        spill_lon=spill_lon,
        detected_at=detected_at,
        corridor=corridor,
    )
    logger.info("Found %d candidate vessel(s)", len(candidates))

    # --- 6. Validate + write Contract C ---
    payload = validate_and_write(source_region=corridor, candidates=candidates)
    logger.info("=== Pipeline complete. Contract C → %s ===", CONTRACT_C_FILE)
    print(json.dumps(payload, indent=2))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 2 — AIS/GIS/Backtracking pipeline for SIH26143"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Write the sample Contract C from the phase doc (no external data)",
    )
    parser.add_argument(
        "--mock-env",
        action="store_true",
        dest="mock_env",
        help="Use mock_env.json for wind/current instead of calling Open-Meteo",
    )
    args = parser.parse_args()

    if args.mock:
        run_mock()
    else:
        run_full(use_mock_env=args.mock_env)


if __name__ == "__main__":
    main()
