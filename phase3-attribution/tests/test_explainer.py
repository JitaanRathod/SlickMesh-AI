"""Tests for explainability reason-string generation and guardrail compliance."""

from explainer import generate_reason_string
from models import SourceRegion, VesselEvidence


def test_guardrails_no_blame_phrasing():
    """Ensure reason strings do not use prohibited blame words."""
    source_region = SourceRegion(latitude=20.0, longitude=67.0, radius_km=20.0, backtrack_hours=24.0)
    evidence = VesselEvidence(
        min_distance_nm=1.0, hours_since_passage=3.0,
        heading_delta_deg=10.0, sog_at_closest_knots=2.0,
        intersects_source_region=True, track_continuity="continuous"
    )
    sub_scores = {
        "environmental_consistency": 0.95,
        "distance": 0.9,
        "time_consistency": 0.85,
        "track_continuity": 0.9,
        "heading": 0.8,
        "speed": 0.9,
        "vessel_type": 1.0
    }

    reason = generate_reason_string("MV Ocean Star", "Tanker", evidence, source_region, sub_scores)

    # Check for forbidden words / absolute claims
    prohibited = ["guilty", "responsible", "caused the spill", "culprit", "perpetrator", "illegal"]
    for word in prohibited:
        assert word not in reason.lower()

    # Check that factual metrics are mentioned
    assert "hours before detection" in reason or "corridor" in reason or "region" in reason


def test_gapped_ais_mention():
    """Ensure discontinuous AIS track is highlighted when present."""
    source_region = SourceRegion(latitude=20.0, longitude=67.0, radius_km=20.0, backtrack_hours=24.0)
    evidence = VesselEvidence(
        min_distance_nm=12.0, hours_since_passage=10.0,
        heading_delta_deg=40.0, sog_at_closest_knots=10.0,
        intersects_source_region=False, track_continuity="gapped"
    )
    sub_scores = {
        "environmental_consistency": 0.2, "distance": 0.3, "time_consistency": 0.4,
        "track_continuity": 0.4, "heading": 0.6, "speed": 0.6, "vessel_type": 0.7
    }

    reason = generate_reason_string("MT Gujarat Pearl", "Cargo", evidence, source_region, sub_scores)
    assert "gaps" in reason.lower() or "discontinuous" in reason.lower() or "outside" in reason.lower()
