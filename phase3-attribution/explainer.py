"""Explainability module for generating human-readable attribution reasons.

Generates transparent, factual, single-sentence explanations derived from the
highest-contributing evidence sub-scores. Adheres strictly to hackathon guardrails
(probabilistic triage only, no legal conclusions).
"""

from typing import Dict, Any, List


def generate_reason_string(
    candidate_name: str,
    vessel_type: str,
    evidence: Any,
    source_region: Any,
    sub_scores: Dict[str, float]
) -> str:
    """Constructs a concise, factual reason string based on prominent signals."""
    d_nm = getattr(evidence, "min_distance_nm", 0.0)
    hrs = getattr(evidence, "hours_since_passage", 0.0)
    intersects = getattr(evidence, "intersects_source_region", False)
    continuity = (getattr(evidence, "track_continuity", "unknown") or "").strip().lower()
    sog = getattr(evidence, "sog_at_closest_knots", 0.0)
    
    is_tanker = any(k in vessel_type.lower() for k in ("tanker", "oil", "crude", "chemical"))
    is_gapped = continuity == "gapped"
    is_slow = sog <= 3.0
    
    if is_gapped:
        if intersects:
            return f"Track intersected estimated source corridor {hrs:.1f} hours prior to detection with recorded AIS transmission gaps."
        else:
            return f"Passed {d_nm:.1f} nm from origin corridor {hrs:.1f} hours before detection with discontinuous AIS broadcast."
            
    if intersects:
        if is_tanker and is_slow:
            return f"Tanker track intersected the backtracked source region {hrs:.1f} hours before detection at slow speed ({sog:.1f} kts)."
        elif is_tanker:
            return f"Tanker track intersected estimated source corridor {hrs:.1f} hours prior to detection (CPA {d_nm:.1f} nm)."
        else:
            return f"Passed within {d_nm:.1f} nm of the backtracked source region {hrs:.1f} hours before detection."
    else:
        if d_nm > (getattr(source_region, "radius_km", 20.0) / 1.852):
            return f"Passed outside the origin corridor at {d_nm:.1f} nm minimum approach distance."
        else:
            return f"Passed within {d_nm:.1f} nm of the backtracked source region {hrs:.1f} hours before detection."


def get_feature_drivers(
    sub_scores: Dict[str, float],
    weights: Dict[str, float]
) -> Dict[str, Any]:
    """Computes weighted contribution and identifies top positive/negative feature drivers."""
    contributions = {k: round(sub_scores.get(k, 0.0) * weights.get(k, 0.0) * 100, 2) for k in weights}
    sorted_factors = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
    
    top_positive = [f"{k} (+{v:.1f}%)" for k, v in sorted_factors[:2] if v > 5.0]
    penalties = [f"{k} ({v:.1f}%)" for k, v in sorted_factors[-2:] if v < 4.0]
    
    return {
        "contributions": contributions,
        "primary_drivers": top_positive,
        "suppression_factors": penalties
    }
