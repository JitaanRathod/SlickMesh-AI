"""Tests for AttributionEngine scoring logic, invariants, and ranking."""

import pytest
from models import BacktrackInput, SourceRegion, CandidateVessel, Position, VesselEvidence
from engine import AttributionEngine, AttributionWeights
from mock_data import get_mock_backtrack_input


def test_attribution_engine_mock_run():
    """Verify engine runs against canonical mock data and produces sorted output."""
    mock_input = get_mock_backtrack_input()
    engine = AttributionEngine()
    output = engine.process(mock_input, spill_id="SPILL-001")

    assert output.spill_id == "SPILL-001"
    assert len(output.ranked_vessels) == 2

    # Top vessel must be MV Ocean Star (intersects corridor, close distance/time)
    top_vessel = output.ranked_vessels[0]
    second_vessel = output.ranked_vessels[1]

    assert top_vessel.name == "MV Ocean Star"
    assert top_vessel.confidence >= second_vessel.confidence
    assert 60 <= top_vessel.confidence <= 100
    assert 0 <= second_vessel.confidence <= 50

    # Output must be sorted descending by confidence
    confidences = [v.confidence for v in output.ranked_vessels]
    assert confidences == sorted(confidences, reverse=True)


def test_attribution_ranking_invariant():
    """Vessel intersecting origin corridor with closer CPA must always outrank distant gapped vessel."""
    engine = AttributionEngine()
    source_region = SourceRegion(latitude=20.0, longitude=67.0, radius_km=20.0, backtrack_hours=24.0)

    # Candidate 1: High risk (close, fast response, continuous)
    c1 = CandidateVessel(
        mmsi="111", name="HighRisk", vessel_type="Tanker",
        position=Position(latitude=20.0, longitude=67.0),
        evidence=VesselEvidence(
            min_distance_nm=1.0, hours_since_passage=2.0,
            heading_delta_deg=5.0, sog_at_closest_knots=2.0,
            intersects_source_region=True, track_continuity="continuous"
        )
    )

    # Candidate 2: Low risk (far, old passage, gapped)
    c2 = CandidateVessel(
        mmsi="222", name="LowRisk", vessel_type="Cargo",
        position=Position(latitude=21.0, longitude=68.0),
        evidence=VesselEvidence(
            min_distance_nm=25.0, hours_since_passage=20.0,
            heading_delta_deg=90.0, sog_at_closest_knots=14.0,
            intersects_source_region=False, track_continuity="gapped"
        )
    )

    input_data = BacktrackInput(source_region=source_region, candidates=[c2, c1])
    result = engine.process(input_data)

    assert result.ranked_vessels[0].name == "HighRisk"
    assert result.ranked_vessels[1].name == "LowRisk"
    assert result.ranked_vessels[0].confidence > result.ranked_vessels[1].confidence


def test_empty_candidates_list():
    """Verify empty candidates list is handled cleanly."""
    engine = AttributionEngine()
    source_region = SourceRegion(latitude=20.0, longitude=67.0, radius_km=20.0, backtrack_hours=24.0)
    input_data = BacktrackInput(source_region=source_region, candidates=[])
    result = engine.process(input_data)
    assert len(result.ranked_vessels) == 0


def test_bayesian_scoring_mode():
    """Verify Bayesian likelihood stretch mode executes and outputs valid probabilities."""
    mock_input = get_mock_backtrack_input()
    engine = AttributionEngine()
    output = engine.process(mock_input, spill_id="SPILL-001", method="bayesian")

    assert len(output.ranked_vessels) == 2
    assert output.ranked_vessels[0].name == "MV Ocean Star"
    for v in output.ranked_vessels:
        assert 0 <= v.confidence <= 100


def test_invalid_weights_sum():
    """Custom weights that do not sum to 1.0 must raise ValueError."""
    with pytest.raises(ValueError):
        AttributionWeights(environmental_consistency=0.9, distance=0.9)
