"""
candidate_matcher.py — Match AIS trajectories to a spill event and compute raw evidence.

This module does NOT produce a combined score — that is Phase 3's job.
It produces exactly the evidence fields specified in Contract C (§9 of phase2-ais-gis-backtracking.md).

Evidence fields per candidate:
  min_distance_nm        — Haversine distance, closest trajectory point to spill centroid
  hours_since_passage    — Elapsed time between closest-approach point and detection time
  heading_delta_deg      — Angle between vessel COG and bearing-to-spill-centroid at closest approach
  sog_at_closest_knots   — Speed at closest approach (low ≈ loitering signal)
  intersects_source_region — Whether the vessel's LineString intersects the buffered origin corridor
  track_continuity       — "continuous" vs "gapped" (a gap near the spill is itself a signal)
"""

import logging
import math
from datetime import datetime, timezone, timedelta

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point
from shapely.wkt import loads as wkt_loads
import movingpandas as mpd

from src.config import (
    LOOKBACK_HOURS,
    CANDIDATE_SEARCH_RADIUS_NM,
    GAP_SPLIT_MINUTES,
)
from src.trajectory_builder import trajectories_to_dataframe

logger = logging.getLogger(__name__)

NM_TO_KM = 1.852
KM_TO_DEG_LAT = 1.0 / 111.0  # rough approximation for lat


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in nautical miles."""
    R_nm = 3440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R_nm * math.asin(math.sqrt(a))


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing (degrees, 0–360) from point 1 → point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _angle_diff(a: float, b: float) -> float:
    """Smallest absolute angular difference between two bearings (0–180°)."""
    diff = abs(a - b) % 360
    return diff if diff <= 180 else 360 - diff


# ---------------------------------------------------------------------------
# Core matching logic
# ---------------------------------------------------------------------------

def _find_closest_point(vessel_df: pd.DataFrame, spill_lat: float, spill_lon: float) -> pd.Series:
    """
    Return the row in vessel_df with the smallest haversine distance to the spill centroid.
    vessel_df must have columns: lat, lon, timestamp
    """
    vessel_df = vessel_df.copy()
    vessel_df["_dist_nm"] = vessel_df.apply(
        lambda r: _haversine_nm(r["lat"], r["lon"], spill_lat, spill_lon), axis=1
    )
    return vessel_df.loc[vessel_df["_dist_nm"].idxmin()]


def _is_track_gapped(vessel_df: pd.DataFrame, near_spill_ts: datetime) -> bool:
    """
    Return True if there is a gap > GAP_SPLIT_MINUTES in the vessel's track
    within ±6 hours of the closest-approach timestamp (deliberate shutoff window).
    """
    window_start = near_spill_ts - timedelta(hours=6)
    window_end = near_spill_ts + timedelta(hours=6)
    ts = vessel_df["timestamp"].sort_values()
    ts_window = ts[(ts >= window_start) & (ts <= window_end)]
    if len(ts_window) < 2:
        return False  # can't tell — treat as continuous
    gaps = ts_window.diff().dropna()
    return bool((gaps > timedelta(minutes=GAP_SPLIT_MINUTES)).any())


def _intersects_corridor(vessel_df: pd.DataFrame, corridor_wkt: str) -> bool:
    """Check if the vessel track (LineString) intersects the buffered origin corridor."""
    try:
        corridor = wkt_loads(corridor_wkt)
        if len(vessel_df) < 2:
            # Single-point track — use point-in-polygon instead
            p = Point(vessel_df.iloc[0]["lon"], vessel_df.iloc[0]["lat"])
            return bool(corridor.contains(p))
        coords = [(row["lon"], row["lat"]) for _, row in vessel_df.iterrows()]
        track_line = LineString(coords)
        return bool(track_line.intersects(corridor))
    except Exception as exc:
        logger.debug("intersects_corridor failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_candidates(
    tc: "mpd.TrajectoryCollection",
    spill_lat: float,
    spill_lon: float,
    detected_at: datetime,
    corridor: dict,
) -> list[dict]:
    """
    Match vessels in `tc` against a spill event and return a list of candidate dicts.

    Parameters
    ----------
    tc : movingpandas.TrajectoryCollection — cleaned trajectories (gap-split)
    spill_lat, spill_lon : float — spill centroid WGS-84
    detected_at : datetime (UTC-aware) — spill detection time
    corridor : dict — output of backtracker.compute_origin_corridor()

    Returns
    -------
    list[dict] — one dict per candidate vessel, with evidence fields.
                 NOT scored / ranked — Phase 3 owns that.
    """
    corridor_wkt = corridor.get("buffered_wkt", "")
    lookback_start = detected_at - timedelta(hours=LOOKBACK_HOURS)

    flat_df = trajectories_to_dataframe(tc)
    if flat_df.empty:
        logger.warning("No trajectory data to match against.")
        return []

    # Ensure timestamps are UTC-aware for comparison
    if flat_df["timestamp"].dt.tz is None:
        flat_df["timestamp"] = flat_df["timestamp"].dt.tz_localize("UTC")
    else:
        flat_df["timestamp"] = flat_df["timestamp"].dt.tz_convert("UTC")

    if detected_at.tzinfo is None:
        detected_at = detected_at.replace(tzinfo=timezone.utc)
    if lookback_start.tzinfo is None:
        lookback_start = lookback_start.replace(tzinfo=timezone.utc)

    # Hard gate: only vessels with ≥1 point in the lookback window
    in_window = flat_df[
        (flat_df["timestamp"] >= lookback_start) & (flat_df["timestamp"] <= detected_at)
    ]

    if in_window.empty:
        logger.warning("No vessels have AIS points in the lookback window.")
        return []

    # Pre-filter to vessels within CANDIDATE_SEARCH_RADIUS_NM of spill centroid
    in_window = in_window.copy()
    in_window["_pre_dist"] = in_window.apply(
        lambda r: _haversine_nm(r["lat"], r["lon"], spill_lat, spill_lon), axis=1
    )
    qualifying_mmsis = in_window[in_window["_pre_dist"] <= CANDIDATE_SEARCH_RADIUS_NM]["mmsi"].unique()
    logger.info(
        "%d unique vessels pass hard gate (window + radius %.0f nm)",
        len(qualifying_mmsis),
        CANDIDATE_SEARCH_RADIUS_NM,
    )

    candidates = []
    for mmsi in qualifying_mmsis:
        vessel_df = flat_df[flat_df["mmsi"] == mmsi].sort_values("timestamp").reset_index(drop=True)
        vessel_window = vessel_df[
            (vessel_df["timestamp"] >= lookback_start)
            & (vessel_df["timestamp"] <= detected_at)
        ]

        if vessel_window.empty:
            continue

        # Closest approach within the lookback window
        closest = _find_closest_point(vessel_window, spill_lat, spill_lon)
        closest_lat = float(closest["lat"])
        closest_lon = float(closest["lon"])
        closest_ts = pd.Timestamp(closest["timestamp"]).to_pydatetime()
        if closest_ts.tzinfo is None:
            closest_ts = closest_ts.replace(tzinfo=timezone.utc)

        min_dist_nm = round(_haversine_nm(closest_lat, closest_lon, spill_lat, spill_lon), 2)
        hours_since = round((detected_at - closest_ts).total_seconds() / 3600, 2)

        # Heading delta at closest approach
        cog_at_closest = float(closest.get("cog", float("nan")))
        bearing_to_spill = _bearing_deg(closest_lat, closest_lon, spill_lat, spill_lon)
        if math.isnan(cog_at_closest):
            heading_delta = None
        else:
            heading_delta = round(_angle_diff(cog_at_closest, bearing_to_spill), 1)

        # SOG at closest approach
        sog = closest.get("sog", None)
        sog_knots = round(float(sog), 2) if sog is not None and not math.isnan(float(sog if sog else 0)) else None

        # Intersects origin corridor
        intersects = _intersects_corridor(vessel_window, corridor_wkt)

        # Track continuity near the spill approach
        is_gapped = _is_track_gapped(vessel_df, closest_ts)
        continuity = "gapped" if is_gapped else "continuous"

        # Latest position within window
        last_row = vessel_window.iloc[-1]
        last_lat = round(float(last_row["lat"]), 6)
        last_lon = round(float(last_row["lon"]), 6)

        # Build track (list of [lat, lon] — AIS convention per Contract C)
        track = [
            [round(float(r["lat"]), 6), round(float(r["lon"]), 6)]
            for _, r in vessel_window.iterrows()
        ]

        # Metadata
        vessel_type = vessel_df["vessel_type"].dropna().iloc[-1] if not vessel_df["vessel_type"].dropna().empty else "Unknown"
        name = vessel_df["name"].dropna().iloc[-1] if not vessel_df["name"].dropna().empty else "Unknown"
        imo = vessel_df["imo"].dropna().iloc[-1] if not vessel_df["imo"].dropna().empty else None

        candidates.append(
            {
                "mmsi": mmsi,
                "imo": str(imo) if imo else None,
                "name": str(name) if name else "Unknown",
                "vessel_type": str(vessel_type) if vessel_type else "Unknown",
                "position": {"latitude": last_lat, "longitude": last_lon},
                "track": track,
                "evidence": {
                    "min_distance_nm": min_dist_nm,
                    "hours_since_passage": hours_since,
                    "heading_delta_deg": heading_delta,
                    "sog_at_closest_knots": sog_knots,
                    "intersects_source_region": intersects,
                    "track_continuity": continuity,
                },
            }
        )

    # Sort by min_distance_nm ascending (closest first — Phase 3 will re-rank by score)
    candidates.sort(key=lambda c: c["evidence"]["min_distance_nm"])
    logger.info("Returning %d candidate vessels", len(candidates))
    return candidates
