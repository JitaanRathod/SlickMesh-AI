"""
ais_cleaner.py — Clean raw AIS data into a standardised Parquet file.

Handles two input formats:
  1. Danish Maritime Authority CSV  (offline dev dataset — identical AIS schema)
  2. NDJSON lines from AISstream.io (live stream output from ais_listener.py)

Usage:
  from src.ais_cleaner import clean_danish_csv, clean_ndjson_stream

Output: cleaned Parquet at config.CLEANED_PARQUET (append mode for stream, overwrite for CSV)
"""

import json
import math
import logging
from pathlib import Path

import pandas as pd
import numpy as np

from src.config import (
    CLEANED_PARQUET,
    RAW_DANISH_CSV,
    RAW_STREAM_FILE,
    MAX_REALISTIC_SPEED_KNOTS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name mapping — Danish CSV → internal names
# ---------------------------------------------------------------------------
DANISH_COLUMN_MAP = {
    "# Timestamp": "timestamp",
    "MMSI": "mmsi",
    "IMO": "imo",
    "Latitude": "lat",
    "Longitude": "lon",
    "SOG": "sog",
    "COG": "cog",
    "Navigational status": "nav_status",
    "Ship type": "vessel_type",
    "Name": "name",
}

REQUIRED_COLUMNS = {"timestamp", "mmsi", "lat", "lon"}


def _knots_to_ms(knots: float) -> float:
    return knots * 0.514444


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in nautical miles between two WGS-84 points."""
    R_nm = 3440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R_nm * math.asin(math.sqrt(a))


def _drop_invalid_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with lat/lon outside valid WGS-84 ranges."""
    before = len(df)
    df = df[(df["lat"].between(-90, 90)) & (df["lon"].between(-180, 180))]
    logger.debug("Coord filter: %d → %d rows", before, len(df))
    return df


def _drop_malformed(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows missing any required field or with MMSI outside valid range."""
    before = len(df)
    df = df.dropna(subset=list(REQUIRED_COLUMNS))
    # MMSI must be a 9-digit number (100 000 000 – 999 999 999)
    df = df[df["mmsi"].astype(str).str.match(r"^\d{9}$")]
    logger.debug("Malformed filter: %d → %d rows", before, len(df))
    return df


def _filter_impossible_jumps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Within each MMSI group, sorted by time, compute implied speed between
    consecutive points and drop ANY point where implied speed > MAX_REALISTIC_SPEED_KNOTS.

    We drop the LATER point (the one we can't trust), not the earlier one.
    """
    df = df.sort_values(["mmsi", "timestamp"])
    df["lat_prev"] = df.groupby("mmsi")["lat"].shift(1)
    df["lon_prev"] = df.groupby("mmsi")["lon"].shift(1)
    df["ts_prev"] = df.groupby("mmsi")["timestamp"].shift(1)

    mask_first = df["lat_prev"].isna()  # first point per vessel — always keep

    # Elapsed hours between consecutive points
    df["dt_h"] = (df["timestamp"] - df["ts_prev"]).dt.total_seconds() / 3600.0

    # Implied speed (nm/h = knots), fill NaN for first rows with 0
    df["implied_speed"] = df.apply(
        lambda r: (
            _haversine_nm(r["lat_prev"], r["lon_prev"], r["lat"], r["lon"]) / r["dt_h"]
            if r["dt_h"] > 0
            else 0.0
        ),
        axis=1,
    )

    before = len(df)
    keep = mask_first | (df["implied_speed"] <= MAX_REALISTIC_SPEED_KNOTS)
    df = df[keep].drop(columns=["lat_prev", "lon_prev", "ts_prev", "dt_h", "implied_speed"])
    logger.debug("Jump filter: %d → %d rows", before, len(df))
    return df


def _standardise(df: pd.DataFrame) -> pd.DataFrame:
    """Cast columns to canonical dtypes."""
    df["mmsi"] = df["mmsi"].astype(str).str.strip()
    df["imo"] = df.get("imo", pd.Series(dtype=str)).astype(str).str.strip().replace({"nan": None, "": None})
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["sog"] = pd.to_numeric(df.get("sog", pd.Series(dtype=float)), errors="coerce")
    df["cog"] = pd.to_numeric(df.get("cog", pd.Series(dtype=float)), errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601", utc=True, errors="coerce")
    for col in ("nav_status", "vessel_type", "name"):
        if col not in df.columns:
            df[col] = None
    return df[["mmsi", "imo", "timestamp", "lat", "lon", "sog", "cog", "nav_status", "vessel_type", "name"]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_danish_csv(csv_path: Path = RAW_DANISH_CSV) -> pd.DataFrame:
    """
    Read one day of Danish Maritime Authority AIS CSV, clean it, write Parquet.

    Returns the cleaned DataFrame.
    """
    logger.info("Reading Danish AIS CSV: %s", csv_path)
    raw = pd.read_csv(csv_path, low_memory=False)
    # Rename only columns that exist in the file to avoid KeyError on partial exports
    rename = {k: v for k, v in DANISH_COLUMN_MAP.items() if k in raw.columns}
    raw = raw.rename(columns=rename)

    df = _standardise(raw)
    df = _drop_malformed(df)
    df = _drop_invalid_coords(df)
    df = df.drop_duplicates(subset=["mmsi", "timestamp"])
    df = _filter_impossible_jumps(df)
    df = df.sort_values(["mmsi", "timestamp"]).reset_index(drop=True)

    logger.info("Cleaned Danish CSV: %d rows → writing %s", len(df), CLEANED_PARQUET)
    df.to_parquet(CLEANED_PARQUET, index=False)
    return df


def clean_ndjson_stream(ndjson_path: Path = RAW_STREAM_FILE) -> pd.DataFrame:
    """
    Parse NDJSON lines produced by ais_listener.py, clean, APPEND to existing Parquet.

    Each line is a raw AISstream.io message dict. We extract the PositionReport payload.
    """
    records = []
    with open(ndjson_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            # AISstream.io wraps the NMEA payload; pull the relevant sub-dict
            payload = msg.get("Message", {}).get("PositionReport", {})
            meta = msg.get("MetaData", {})
            if not payload:
                continue

            records.append(
                {
                    "mmsi": str(meta.get("MMSI", "")),
                    "imo": None,  # not in PositionReport; enriched later from ShipStaticData
                    "timestamp": meta.get("time_utc"),
                    "lat": payload.get("Latitude"),
                    "lon": payload.get("Longitude"),
                    "sog": payload.get("Sog"),
                    "cog": payload.get("Cog"),
                    "nav_status": payload.get("NavigationalStatus"),
                    "vessel_type": None,
                    "name": meta.get("ShipName"),
                }
            )

    if not records:
        logger.warning("No valid AISstream records found in %s", ndjson_path)
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = _standardise(df)
    df = _drop_malformed(df)
    df = _drop_invalid_coords(df)
    df = df.drop_duplicates(subset=["mmsi", "timestamp"])
    df = _filter_impossible_jumps(df)
    df = df.sort_values(["mmsi", "timestamp"]).reset_index(drop=True)

    # Append to existing Parquet (or create if absent)
    if CLEANED_PARQUET.exists():
        existing = pd.read_parquet(CLEANED_PARQUET)
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["mmsi", "timestamp"])
        combined.to_parquet(CLEANED_PARQUET, index=False)
        logger.info("Appended %d new rows; Parquet now has %d rows", len(df), len(combined))
        return combined
    else:
        df.to_parquet(CLEANED_PARQUET, index=False)
        logger.info("Created Parquet with %d rows (stream only)", len(df))
        return df
