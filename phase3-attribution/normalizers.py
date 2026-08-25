"""Feature normalizers for vessel attribution evidence metrics.

Transforms raw physical, temporal, spatial, and contextual metrics into
normalized sub-scores bounded strictly in [0.0, 1.0].
"""

import math
from typing import Dict, Any


def normalize_environmental_consistency(
    intersects_source_region: bool,
    min_distance_nm: float,
    radius_km: float
) -> float:
    """Computes environmental corridor consistency score.

    Acts as a near-gate signal: inside the corridor yields high consistency (0.85-1.0),
    whereas falling outside incurs a steep penalty.
    """
    try:
        r_km = max(0.1, float(radius_km))
        d_nm = max(0.0, float(min_distance_nm))
    except (TypeError, ValueError):
        r_km = 20.0
        d_nm = 0.0

    radius_nm = max(0.1, r_km / 1.852)
    if bool(intersects_source_region) or d_nm <= (radius_nm * 0.5):
        decay = min(0.15, (d_nm / radius_nm) * 0.15)
        return round(max(0.75, min(1.0, 1.0 - decay)), 3)
    
    # Outside corridor: suppression curve
    ratio = d_nm / radius_nm
    penalized = max(0.0, 0.45 - (ratio - 0.5) * 0.35)
    return round(max(0.0, min(1.0, penalized)), 3)


def normalize_distance(min_distance_nm: float, radius_km: float) -> float:
    """Normalizes closest point of approach against source corridor radius.

    Normalizing against the adaptive uncertainty corridor radius rather than a
    fixed absolute distance ensures fairness across varying drift simulation scales.
    """
    try:
        r_km = max(0.1, float(radius_km))
        d_nm = max(0.0, float(min_distance_nm))
    except (TypeError, ValueError):
        r_km = 20.0
        d_nm = 0.0

    radius_nm = max(0.1, r_km / 1.852)
    max_effective_dist = radius_nm * 1.3
    if d_nm >= max_effective_dist:
        return 0.0
    score = 1.0 - (d_nm / max_effective_dist)
    return round(max(0.0, min(1.0, score)), 3)


def normalize_time(hours_since_passage: float, backtrack_hours: float = 24.0) -> float:
    """Normalizes the temporal proximity of vessel passage relative to detection time.

    Passage close to estimated origin time yields higher likelihood; passages outside
    the simulation window yield zero.
    """
    try:
        t_hrs = max(0.0, float(hours_since_passage))
        b_hrs = max(1.0, float(backtrack_hours))
    except (TypeError, ValueError):
        t_hrs = 0.0
        b_hrs = 24.0

    effective_window = b_hrs * 1.15
    if t_hrs >= effective_window:
        return 0.0
    score = 1.0 - (t_hrs / effective_window)
    return round(max(0.0, min(1.0, score)), 3)


def normalize_heading(heading_delta_deg: float) -> float:
    """Normalizes heading compatibility against drift angle.

    0 deg difference (aligned with drift/slick trajectory) -> 1.0
    180 deg difference (opposite direction) -> 0.0
    """
    try:
        deg = abs(float(heading_delta_deg)) % 360.0
    except (TypeError, ValueError):
        deg = 0.0

    if deg > 180.0:
        deg = 360.0 - deg
    score = 1.0 - (deg / 180.0)
    return round(max(0.0, min(1.0, score)), 3)


def normalize_speed(sog_at_closest_knots: float) -> float:
    """Evaluates Speed Over Ground (SOG) consistency.

    Near-zero or low speed (<3 knots) near origin region may indicate loitering /
    discharging behavior. Normal transit (8-14 kts) is standard. Very high speeds (>20 kts)
    are atypical for bulk liquid transport.
    """
    try:
        sog = max(0.0, float(sog_at_closest_knots))
    except (TypeError, ValueError):
        sog = 0.0

    if sog <= 2.5:
        return 0.90
    elif sog <= 6.0:
        return 0.80
    elif sog <= 12.0:
        return 0.65
    elif sog <= 18.0:
        return 0.50
    else:
        return 0.30


def normalize_vessel_type(vessel_type: str) -> float:
    """Provides a soft contextual prior based on vessel cargo category.

    Never acts as a hard filter: non-tankers still carry bunker fuel.
    """
    vt = (vessel_type or "").strip().lower()
    if any(k in vt for k in ("tanker", "crude", "chemical", "oil", "petroleum", "lng", "lpg", "vlcc", "suezmax")):
        return 1.0
    elif any(k in vt for k in ("cargo", "container", "bulk", "freighter", "carrier")):
        return 0.70
    elif any(k in vt for k in ("tug", "offshore", "supply", "towing", "utility", "dredger")):
        return 0.60
    elif any(k in vt for k in ("fishing", "passenger", "ferry", "pleasure", "yacht")):
        return 0.40
    else:
        return 0.50


def normalize_continuity(track_continuity: str) -> float:
    """Scores AIS broadcast continuity through the surveillance zone.

    Continuous track -> 0.90
    Gapped track -> 0.40 (flags possible transponder disabling or signal loss)
    Unknown -> 0.50
    """
    tc = (track_continuity or "").strip().lower()
    if tc == "continuous":
        return 0.90
    elif tc == "gapped":
        return 0.40
    else:
        return 0.50


def compute_all_subscores(
    evidence: Any,
    source_region: Any,
    vessel_type: str
) -> Dict[str, float]:
    """Extracts and normalizes all 7 evidence features into a dictionary."""
    return {
        "environmental_consistency": normalize_environmental_consistency(
            getattr(evidence, "intersects_source_region", False),
            getattr(evidence, "min_distance_nm", 0.0),
            getattr(source_region, "radius_km", 20.0)
        ),
        "distance": normalize_distance(
            getattr(evidence, "min_distance_nm", 0.0),
            getattr(source_region, "radius_km", 20.0)
        ),
        "time_consistency": normalize_time(
            getattr(evidence, "hours_since_passage", 0.0),
            getattr(source_region, "backtrack_hours", 24.0)
        ),
        "track_continuity": normalize_continuity(
            getattr(evidence, "track_continuity", "unknown")
        ),
        "heading": normalize_heading(
            getattr(evidence, "heading_delta_deg", 0.0)
        ),
        "speed": normalize_speed(
            getattr(evidence, "sog_at_closest_knots", 0.0)
        ),
        "vessel_type": normalize_vessel_type(
            vessel_type
        )
    }
