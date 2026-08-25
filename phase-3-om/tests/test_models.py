"""Tests for Pydantic schema validation of Contract C and Contract D."""

import pytest
from pydantic import ValidationError

from models import (
    SourceRegion,
    Position,
    VesselEvidence,
    CandidateVessel,
    BacktrackInput,
    SubScores,
    RankedVessel,
    AttributionOutput
)
from mock_data import MOCK_CONTRACT_C_DATA, MOCK_CONTRACT_D_DATA


def test_contract_c_mock_parsing():
    """Verify that canonical mock Contract C parses cleanly."""
    parsed = BacktrackInput.model_validate(MOCK_CONTRACT_C_DATA)
    assert parsed.source_region.radius_km == 22.0
    assert len(parsed.candidates) == 2
    assert parsed.candidates[0].mmsi == "419001234"
    assert parsed.candidates[0].evidence.intersects_source_region is True


def test_contract_d_mock_parsing():
    """Verify that canonical mock Contract D parses cleanly."""
    parsed = AttributionOutput.model_validate(MOCK_CONTRACT_D_DATA)
    assert parsed.spill_id == "SPILL-001"
    assert len(parsed.ranked_vessels) == 1
    assert parsed.ranked_vessels[0].confidence == 79
    assert parsed.ranked_vessels[0].sub_scores.environmental_consistency == 0.9


def test_evidence_track_continuity_normalization():
    """Verify that track_continuity accepts mixed case and unknown values gracefully."""
    ev1 = VesselEvidence(
        min_distance_nm=2.0,
        hours_since_passage=1.0,
        track_continuity="CONTINUOUS"
    )
    assert ev1.track_continuity == "continuous"

    ev2 = VesselEvidence(
        min_distance_nm=2.0,
        hours_since_passage=1.0,
        track_continuity="invalid_value"
    )
    assert ev2.track_continuity == "unknown"


def test_invalid_confidence_range():
    """Verify that confidence outside [0, 100] raises validation error."""
    sub_scores = SubScores(
        environmental_consistency=0.9,
        distance=0.8,
        time_consistency=0.7,
        track_continuity=0.8,
        heading=0.7,
        speed=0.6,
        vessel_type=1.0
    )
    with pytest.raises(ValidationError):
        RankedVessel(
            mmsi="123456789",
            name="Test Vessel",
            vessel_type="Tanker",
            confidence=105,  # > 100
            reason="Test",
            sub_scores=sub_scores
        )
