"""
trajectory_builder.py — Build per-vessel trajectories from cleaned AIS data.

Uses movingpandas to:
- Group records by MMSI
- Sort by timestamp
- Split on AIS gaps > GAP_SPLIT_MINUTES (silence is evidence — don't smooth over it)
- Clip to the Arabian Sea / Bay of Bengal area of interest
- Return a movingpandas TrajectoryCollection for use by candidate_matcher.py

Usage:
  from src.trajectory_builder import build_trajectories
  traj_collection = build_trajectories(cleaned_df)
"""

import logging
from datetime import timedelta

import geopandas as gpd
import movingpandas as mpd
import pandas as pd
from shapely.geometry import Point

from src.config import (
    BOUNDING_BOX,
    CLEANED_PARQUET,
    GAP_SPLIT_MINUTES,
)

logger = logging.getLogger(__name__)

# AoI polygon (bounding box) for clipping trajectories
# BOUNDING_BOX: [[min_lat, min_lon], [max_lat, max_lon]]
_AOI_MIN_LAT = BOUNDING_BOX[0][0]
_AOI_MIN_LON = BOUNDING_BOX[0][1]
_AOI_MAX_LAT = BOUNDING_BOX[1][0]
_AOI_MAX_LON = BOUNDING_BOX[1][1]


def _load_cleaned(parquet_path=CLEANED_PARQUET) -> pd.DataFrame:
    """Load cleaned Parquet produced by ais_cleaner.py."""
    df = pd.read_parquet(parquet_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def _to_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Convert flat DataFrame to GeoDataFrame with Point geometry."""
    geometry = [Point(row.lon, row.lat) for row in df.itertuples(index=False)]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    gdf = gdf.set_index("timestamp")
    gdf.index = gdf.index.tz_localize(None) if gdf.index.tzinfo is None else gdf.index.tz_convert(None)
    return gdf


def _clip_to_aoi(tc: mpd.TrajectoryCollection) -> mpd.TrajectoryCollection:
    """
    Keep only trajectories (or trajectory segments) that have at least one
    point inside the Arabian Sea / Bay of Bengal bounding box.

    movingpandas does not expose a direct bounding-box clip on a collection,
    so we filter at the DataFrame level before building the collection.
    """
    return tc  # AoI filter already applied upstream in build_trajectories


def build_trajectories(df: pd.DataFrame | None = None) -> mpd.TrajectoryCollection:
    """
    Main entry point.

    Parameters
    ----------
    df : pd.DataFrame, optional
        Pre-loaded cleaned AIS DataFrame. If None, loads from CLEANED_PARQUET.

    Returns
    -------
    mpd.TrajectoryCollection
        One trajectory (or gap-split sub-trajectory) per MMSI segment.
    """
    if df is None:
        logger.info("Loading cleaned AIS data from Parquet …")
        df = _load_cleaned()

    logger.info("Input: %d AIS points across %d unique MMSIs", len(df), df["mmsi"].nunique())

    # Clip to AoI before building trajectories (much faster than clipping post-hoc)
    mask_aoi = (
        df["lat"].between(_AOI_MIN_LAT, _AOI_MAX_LAT)
        & df["lon"].between(_AOI_MIN_LON, _AOI_MAX_LON)
    )
    df_aoi = df[mask_aoi].copy()
    logger.info("After AoI clip: %d points, %d unique MMSIs", len(df_aoi), df_aoi["mmsi"].nunique())

    if df_aoi.empty:
        logger.warning("No AIS data inside AoI after clipping — returning empty collection.")
        return mpd.TrajectoryCollection([], traj_id_col="mmsi")

    gdf = _to_geodataframe(df_aoi)

    # Build TrajectoryCollection grouped by MMSI
    tc = mpd.TrajectoryCollection(
        gdf,
        traj_id_col="mmsi",
        min_length=0,   # keep even short 1-point tracks — they carry temporal evidence
    )

    logger.info("Built %d raw trajectories", len(tc))

    # Split on gaps > GAP_SPLIT_MINUTES — a long AIS silence near a spill is evidence, not noise
    tc = mpd.ObservationGapSplitter(tc).split(gap=timedelta(minutes=GAP_SPLIT_MINUTES))
    logger.info("After gap-split: %d trajectory segments", len(tc))

    return tc


def trajectories_to_dataframe(tc: mpd.TrajectoryCollection) -> pd.DataFrame:
    """
    Flatten a TrajectoryCollection back to a tidy DataFrame for easier
    math in candidate_matcher.py.

    Returns columns: traj_id, mmsi, timestamp, lat, lon, sog, cog, ...
    """
    rows = []
    for traj in tc.trajectories:
        gdf = traj.df.copy().reset_index()
        gdf["traj_id"] = traj.id
        gdf["mmsi"] = str(traj.id).split("_")[0]  # strip gap-split suffix
        gdf["lat"] = gdf.geometry.y
        gdf["lon"] = gdf.geometry.x
        rows.append(gdf)

    if not rows:
        return pd.DataFrame()

    flat = pd.concat(rows, ignore_index=True)
    flat = flat.rename(columns={"index": "timestamp"})
    return flat
