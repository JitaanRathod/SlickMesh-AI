"""
backtracker.py — Simplified single-vector reverse drift origin corridor.

Algorithm (first-order, explicitly NOT a full Lagrangian simulation):
  1. Take spill centroid + detection time T.
  2. Pull average wind vector + average ocean-current vector at that location/time
     from Open-Meteo Marine API (no key required).
  3. drift_vector = current_vector + windage_fraction × wind_vector
     (windage ≈ 3 % of wind speed, in wind direction — standard first-order approximation)
  4. Project this vector BACKWARD from the spill location over `lookback_hours`.
  5. Build a buffered LineString → origin corridor (buffered, NOT a single point).

References / prior art:
  - GNOME (NOAA): same first-order vector field, adds Lagrangian particles + diffusion.
  - MV Rak (Mumbai, 2011) and MSC ELSA III (Kochi, 2025): validate this simplified approach
    is applicable to Indian waters / Arabian Sea scenarios.

Explicitly out of scope tonight:
  - Time-varying wind/current fields over the whole window (we use one averaged vector)
  - Forward-backward drift convergence (GNOME stretch)
  - Oil weathering / evaporation effects
  These are documented as future work, not omissions.
"""

import json
import logging
import math
from pathlib import Path

import requests
from shapely.geometry import LineString, Point
from shapely.ops import transform
import pyproj

from src.config import (
    CORRIDOR_BUFFER_KM,
    LOOKBACK_HOURS,
    WINDAGE_FRACTION,
)

logger = logging.getLogger(__name__)

OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


# ---------------------------------------------------------------------------
# Wind / current fetching
# ---------------------------------------------------------------------------

def _fetch_open_meteo_env(lat: float, lon: float) -> dict:
    """
    Pull current + wind at (lat, lon) from Open-Meteo (no API key needed).

    Returns dict with keys: current_u_ms, current_v_ms, wind_speed_ms, wind_direction_deg
    Raises RuntimeError if both marine and forecast endpoints fail.
    """
    # Marine API — ocean currents
    marine_ok = False
    current_u, current_v = 0.0, 0.0
    try:
        r = requests.get(
            OPEN_METEO_MARINE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": ["ocean_current_velocity", "ocean_current_direction"],
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("current", {})
        speed_ms = float(data.get("ocean_current_velocity", 0) or 0)
        direction_deg = float(data.get("ocean_current_direction", 0) or 0)
        # Convert polar (speed + direction) to Cartesian (u=east, v=north)
        rad = math.radians(direction_deg)
        current_u = speed_ms * math.sin(rad)   # eastward component
        current_v = speed_ms * math.cos(rad)   # northward component
        marine_ok = True
        logger.info("Open-Meteo Marine: current %.3f m/s @ %.1f°", speed_ms, direction_deg)
    except Exception as exc:
        logger.warning("Open-Meteo Marine API failed (%s) — current set to 0", exc)

    # Forecast API — wind
    wind_speed_ms, wind_direction_deg = 0.0, 0.0
    try:
        r = requests.get(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
            },
            timeout=10,
        )
        r.raise_for_status()
        wx = r.json().get("current_weather", {})
        wind_speed_ms = float(wx.get("windspeed", 0) or 0) / 3.6  # km/h → m/s
        wind_direction_deg = float(wx.get("winddirection", 0) or 0)
        logger.info("Open-Meteo Forecast: wind %.2f m/s @ %.1f°", wind_speed_ms, wind_direction_deg)
    except Exception as exc:
        logger.warning("Open-Meteo Forecast API failed (%s) — wind set to 0", exc)

    if not marine_ok and wind_speed_ms == 0:
        raise RuntimeError("Both Open-Meteo endpoints failed. Use mock_env.json as fallback.")

    return {
        "current_u_ms": current_u,
        "current_v_ms": current_v,
        "wind_speed_ms": wind_speed_ms,
        "wind_direction_deg": wind_direction_deg,
        "source_model": "Open-Meteo",
    }


def _load_mock_env(mock_path: Path) -> dict:
    """Load mock Contract B JSON as a fallback."""
    with open(mock_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Drift computation
# ---------------------------------------------------------------------------

def _compute_drift_vector(env: dict) -> tuple[float, float]:
    """
    Compute combined drift vector (u, v) in m/s from ocean current + windage.

    drift = current + windage_fraction × wind_vector
    """
    wind_rad = math.radians(env["wind_direction_deg"])
    wind_u = env["wind_speed_ms"] * math.sin(wind_rad)
    wind_v = env["wind_speed_ms"] * math.cos(wind_rad)

    drift_u = env["current_u_ms"] + WINDAGE_FRACTION * wind_u
    drift_v = env["current_v_ms"] + WINDAGE_FRACTION * wind_v
    return drift_u, drift_v


def _project_point_backward(
    lat: float,
    lon: float,
    drift_u_ms: float,
    drift_v_ms: float,
    hours: float,
) -> tuple[float, float]:
    """
    Move a WGS-84 point BACKWARD along the drift vector for `hours` hours.

    Uses azimuthal equidistant projection centred on the starting point so
    we can work in metres and avoid haversine approximation errors.
    """
    proj = pyproj.Proj(proj="aeqd", lat_0=lat, lon_0=lon, datum="WGS84")
    wgs84 = pyproj.Proj(proj="latlong", datum="WGS84")
    transformer_to_m = pyproj.Transformer.from_proj(wgs84, proj, always_xy=True)
    transformer_to_ll = pyproj.Transformer.from_proj(proj, wgs84, always_xy=True)

    seconds = hours * 3600
    dx = -drift_u_ms * seconds  # backward → negate
    dy = -drift_v_ms * seconds

    origin_x, origin_y = transformer_to_m.transform(lon, lat)
    dest_x = origin_x + dx
    dest_y = origin_y + dy
    dest_lon, dest_lat = transformer_to_ll.transform(dest_x, dest_y)
    return dest_lat, dest_lon


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_origin_corridor(
    spill_lat: float,
    spill_lon: float,
    mock_env_path: Path | None = None,
    lookback_hours: int = LOOKBACK_HOURS,
) -> dict:
    """
    Compute the reverse-drift origin corridor for a given spill centroid.

    Parameters
    ----------
    spill_lat, spill_lon : floats — spill centroid in WGS-84
    mock_env_path : Path, optional — if set, use this Contract B JSON instead of calling Open-Meteo
    lookback_hours : int — time window to backtrack over (default from config)

    Returns
    -------
    dict with keys:
      latitude, longitude,  ← centroid of the origin corridor
      radius_km,            ← corridor width = CORRIDOR_BUFFER_KM
      backtrack_hours,      ← lookback used
      origin_line,          ← list of [lat, lon] waypoints along backtrack path (internal use)
      buffered_wkt,         ← WKT of the buffered origin corridor geometry (for intersects check)
    """
    # 1. Get environmental data
    if mock_env_path is not None:
        logger.info("Using mock env from %s", mock_env_path)
        env = _load_mock_env(mock_env_path)
    else:
        try:
            env = _fetch_open_meteo_env(spill_lat, spill_lon)
        except RuntimeError as e:
            logger.error("%s", e)
            raise

    # 2. Compute drift vector
    drift_u, drift_v = _compute_drift_vector(env)
    logger.info("Drift vector: u=%.4f m/s (east), v=%.4f m/s (north)", drift_u, drift_v)

    # 3. Project backward — build a simple 2-point line: spill_centroid → estimated_origin
    #    (could be extended to multi-step for curving drift tracks in future)
    origin_lat, origin_lon = _project_point_backward(
        spill_lat, spill_lon, drift_u, drift_v, lookback_hours
    )
    logger.info(
        "Estimated origin: lat=%.4f, lon=%.4f (backtracked %d h)",
        origin_lat,
        origin_lon,
        lookback_hours,
    )

    # 4. Build origin corridor as a buffered LineString in projected metres
    #    Project to azimuthal equidistant from spill centroid, buffer in km → m, back to WGS84
    wgs84 = pyproj.CRS("EPSG:4326")
    aeqd = pyproj.CRS(
        proj="aeqd", lat_0=spill_lat, lon_0=spill_lon, datum="WGS84"
    )
    to_aeqd = pyproj.Transformer.from_crs(wgs84, aeqd, always_xy=True).transform
    to_wgs84 = pyproj.Transformer.from_crs(aeqd, wgs84, always_xy=True).transform

    line_wgs84 = LineString([(spill_lon, spill_lat), (origin_lon, origin_lat)])
    line_aeqd = transform(to_aeqd, line_wgs84)
    buffered_aeqd = line_aeqd.buffer(CORRIDOR_BUFFER_KM * 1000)
    buffered_wgs84 = transform(to_wgs84, buffered_aeqd)

    # 5. Corridor radius for Contract C (just the buffer, not the full LineString length)
    # Approximate total corridor half-width as buffer + line half-length → keep it simple
    corridor_km = round(
        math.sqrt((origin_lat - spill_lat) ** 2 + (origin_lon - spill_lon) ** 2) * 111 / 2
        + CORRIDOR_BUFFER_KM,
        1,
    )

    return {
        "latitude": round((spill_lat + origin_lat) / 2, 6),   # midpoint of corridor
        "longitude": round((spill_lon + origin_lon) / 2, 6),
        "radius_km": corridor_km,
        "backtrack_hours": lookback_hours,
        # Internal fields (not part of Contract C source_region directly):
        "origin_lat": origin_lat,
        "origin_lon": origin_lon,
        "buffered_wkt": buffered_wgs84.wkt,
        "env": env,
    }
