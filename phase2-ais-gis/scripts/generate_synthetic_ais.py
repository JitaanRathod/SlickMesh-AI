"""
generate_synthetic_ais.py — Generate realistic synthetic AIS data for Arabian Sea testing.

Generates vessel tracks in the Arabian Sea around the mock spill location (20.48 N, 67.52 E)
across the 24-hour lookback window (2026-08-24 06:00 UTC to 2026-08-25 06:00 UTC).

Output:
  Writes directly to data/ais_cleaned.parquet

Usage:
  python scripts/generate_synthetic_ais.py
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import CLEANED_PARQUET, DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generate_synthetic_data() -> pd.DataFrame:
    spill_lat, spill_lon = 20.48, 67.52
    end_time = datetime(2026, 8, 25, 6, 0, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(hours=24)

    # 4 synthetic vessels with different realistic trajectories
    vessels = [
        {
            "mmsi": "419001234",
            "imo": "9123456",
            "name": "MV Ocean Star",
            "vessel_type": "Tanker",
            "start_lat": 19.50,
            "start_lon": 66.20,
            "end_lat": 20.60,
            "end_lon": 67.65,
            "sog": 12.5,
            "cog": 45.0,
            "gap": False,
        },
        {
            "mmsi": "419005678",
            "imo": "9567890",
            "name": "MT Arabian Trader",
            "vessel_type": "Tanker",
            "start_lat": 20.80,
            "start_lon": 67.90,
            "end_lat": 19.90,
            "end_lon": 66.80,
            "sog": 14.0,
            "cog": 225.0,
            "gap": True, # Has an AIS gap near passage
        },
        {
            "mmsi": "419009999",
            "imo": "9999999",
            "name": "SS Sindhu Express",
            "vessel_type": "Cargo",
            "start_lat": 21.50,
            "start_lon": 68.20,
            "end_lat": 21.80,
            "end_lon": 68.80,
            "sog": 10.0,
            "cog": 60.0,
            "gap": False,
        },
        {
            "mmsi": "419003333",
            "imo": "9333333",
            "name": "MV Sea Gull",
            "vessel_type": "Container",
            "start_lat": 18.80,
            "start_lon": 67.00,
            "end_lat": 19.20,
            "end_lon": 67.50,
            "sog": 15.0,
            "cog": 50.0,
            "gap": False,
        },
    ]

    records = []

    for v in vessels:
        # Ping every 10 minutes over 24 hours (145 points)
        timestamps = [start_time + timedelta(minutes=10 * i) for i in range(145)]
        num_pts = len(timestamps)

        lats = np.linspace(v["start_lat"], v["end_lat"], num_pts)
        lons = np.linspace(v["start_lon"], v["end_lon"], num_pts)

        # Add small random noise to make tracks realistic
        lats += np.random.normal(0, 0.005, num_pts)
        lons += np.random.normal(0, 0.005, num_pts)

        for i in range(num_pts):
            ts = timestamps[i]
            # Simulate AIS gap if configured for this vessel around hours 8 to 14
            if v["gap"] and 45 <= i <= 85:
                continue

            records.append({
                "mmsi": v["mmsi"],
                "imo": v["imo"],
                "timestamp": ts,
                "lat": float(round(lats[i], 6)),
                "lon": float(round(lons[i], 6)),
                "sog": float(v["sog"]),
                "cog": float(v["cog"]),
                "nav_status": 0,
                "vessel_type": v["vessel_type"],
                "name": v["name"],
            })

    df = pd.DataFrame(records)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CLEANED_PARQUET, index=False)
    logger.info("Generated %d synthetic AIS records across %d vessels -> %s", len(df), len(vessels), CLEANED_PARQUET)
    return df


if __name__ == "__main__":
    generate_synthetic_data()
