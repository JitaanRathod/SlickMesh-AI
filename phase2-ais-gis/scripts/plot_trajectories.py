"""
plot_trajectories.py — Sanity-check visualiser for Phase 2.

Plots:
  - Cleaned vessel trajectories in the AoI
  - Spill centroid (red star)
  - Backtracked origin corridor (orange shaded region)
  - Candidate vessels highlighted in red

Usage:
  cd phase2-ais-gis
  python scripts/plot_trajectories.py                   # reads output/contract_c.json + data/ais_cleaned.parquet
  python scripts/plot_trajectories.py --save plot.png   # save instead of showing interactively
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
from shapely.wkt import loads as wkt_loads
from shapely.geometry import mapping
import numpy as np

from src.config import CLEANED_PARQUET, CONTRACT_C_FILE, BOUNDING_BOX


def load_contract_c(path: Path = CONTRACT_C_FILE) -> dict:
    if not path.exists():
        print(f"[ERROR] Contract C not found at {path}. Run run_pipeline.py first.")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def plot(save_path: str | None = None) -> None:
    contract = load_contract_c()
    sr = contract["source_region"]
    candidates = contract["candidates"]
    candidate_mmsis = {c["mmsi"] for c in candidates}

    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_facecolor("#0d1b2a")
    fig.patch.set_facecolor("#0d1b2a")

    # --- AoI bounding box hint ---
    ax.set_xlim(BOUNDING_BOX[0][1], BOUNDING_BOX[1][1])
    ax.set_ylim(BOUNDING_BOX[0][0], BOUNDING_BOX[1][0])

    # --- All vessel trajectories (dim) ---
    if CLEANED_PARQUET.exists():
        df = pd.read_parquet(CLEANED_PARQUET)
        for mmsi, grp in df.groupby("mmsi"):
            grp = grp.sort_values("timestamp")
            color = "#e63946" if str(mmsi) in candidate_mmsis else "#457b9d"
            alpha = 0.9 if str(mmsi) in candidate_mmsis else 0.15
            lw = 1.8 if str(mmsi) in candidate_mmsis else 0.5
            ax.plot(grp["lon"], grp["lat"], color=color, alpha=alpha, linewidth=lw)

    # --- Candidate tracks from Contract C (bolder, with markers) ---
    for c in candidates:
        track = c["track"]
        lats = [p[0] for p in track]
        lons = [p[1] for p in track]
        ax.plot(lons, lats, color="#e63946", linewidth=2.5, zorder=5)
        ax.scatter(lons[-1], lats[-1], color="#e63946", s=60, zorder=6, marker="^",
                   label=f"{c['name']} ({c['mmsi']})")
        ax.annotate(
            c["name"],
            xy=(lons[-1], lats[-1]),
            xytext=(5, 5),
            textcoords="offset points",
            color="white",
            fontsize=7,
            zorder=7,
        )

    # --- Origin corridor (orange shaded polygon) ---
    # Approximate with a circle centred on the corridor midpoint
    corridor_lat = sr["latitude"]
    corridor_lon = sr["longitude"]
    radius_deg = sr["radius_km"] / 111.0
    theta = np.linspace(0, 2 * np.pi, 120)
    cx = corridor_lon + radius_deg * np.cos(theta)
    cy = corridor_lat + radius_deg * np.sin(theta)
    ax.fill(cx, cy, color="#f4a261", alpha=0.25, zorder=3, label=f"Origin corridor (r≈{sr['radius_km']} km)")
    ax.plot(cx, cy, color="#f4a261", linewidth=1.2, alpha=0.7, zorder=4)

    # --- Spill centroid (bright red star) ---
    spill_path = Path(__file__).parent.parent / "mock_spill.json"
    if spill_path.exists():
        with open(spill_path) as f:
            spill = json.load(f)
        spill_lat = spill["centroid"]["lat"]
        spill_lon = spill["centroid"]["lon"]
        ax.scatter(spill_lon, spill_lat, color="#ff595e", s=220, marker="*", zorder=8,
                   label=f"Spill centroid ({spill_lon:.2f}°E, {spill_lat:.2f}°N)")
        ax.annotate(
            "SPILL",
            xy=(spill_lon, spill_lat),
            xytext=(6, 6),
            textcoords="offset points",
            color="#ff595e",
            fontsize=9,
            fontweight="bold",
            zorder=9,
        )

    # --- Formatting ---
    ax.set_xlabel("Longitude (°E)", color="white", fontsize=11)
    ax.set_ylabel("Latitude (°N)", color="white", fontsize=11)
    ax.set_title(
        "Phase 2 — AIS Trajectories, Origin Corridor & Candidate Vessels\n"
        f"(Backtrack: {sr['backtrack_hours']}h | Candidates: {len(candidates)})",
        color="white",
        fontsize=13,
        pad=12,
    )
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")

    legend = ax.legend(loc="upper right", facecolor="#1e293b", edgecolor="#475569", labelcolor="white", fontsize=8)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, facecolor=fig.get_facecolor())
        print(f"Plot saved to {save_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description="Phase 2 trajectory sanity-check plot")
    parser.add_argument("--save", metavar="FILE", help="Save plot to file instead of showing")
    args = parser.parse_args()
    plot(save_path=args.save)


if __name__ == "__main__":
    main()
