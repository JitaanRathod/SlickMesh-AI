"""Tests for edge cases, null values, and extreme inputs."""

import pytest
from engine import AttributionEngine
from models import BacktrackInput, SourceRegion, CandidateVessel, Position, VesselEvidence


def test_extreme_and_null_numeric_values():
    """Ensure engine handles zero/negative/infinite values gracefully without crashing."""
    engine = AttributionEngine()
    
    # Extreme candidate with zero distances and extreme values
    c1 = CandidateVessel(
        mmsi="9990001",
        name="Boundary Tester",
        vessel_type="Crude Oil Tanker",
        position=Position(latitude=0.0, longitude=0.0),
        evidence=VesselEvidence(
            min_distance_nm=0.0,
            hours_since_passage=0.0,
            heading_delta_deg=720.0,  # Multi-rotation
            sog_at_closest_knots=0.0,
            intersects_source_region=True,
            track_continuity="continuous"
        )
    )
    
    source = SourceRegion(latitude=0.0, longitude=0.0, radius_km=10.0, backtrack_hours=12.0)
    data = BacktrackInput(source_region=source, candidates=[c1])
    
    result = engine.process(data)
    assert len(result.ranked_vessels) == 1
    assert 0 <= result.ranked_vessels[0].confidence <= 100
    assert result.ranked_vessels[0].sub_scores.environmental_consistency == 1.0
    assert result.ranked_vessels[0].sub_scores.distance == 1.0
    assert result.ranked_vessels[0].sub_scores.time_consistency == 1.0


def test_dict_and_json_string_process_inputs():
    """Test that engine.process accepts raw dicts and JSON strings directly."""
    engine = AttributionEngine()
    raw_dict = {
        "source_region": {"latitude": 20.0, "longitude": 67.0, "radius_km": 15.0},
        "candidates": [
            {
                "mmsi": "123", "name": "V1", "vessel_type": "Tanker",
                "position": {"latitude": 20.0, "longitude": 67.0},
                "evidence": {"min_distance_nm": 1.0, "hours_since_passage": 2.0, "intersects_source_region": True}
            }
        ]
    }
    
    # Raw dict input
    res1 = engine.process(raw_dict)
    assert len(res1.ranked_vessels) == 1
    
    # JSON string input
    import json
    res2 = engine.process(json.dumps(raw_dict))
    assert len(res2.ranked_vessels) == 1
    assert res1.ranked_vessels[0].confidence == res2.ranked_vessels[0].confidence


def test_ascii_table_rendering():
    """Test ASCII report rendering output contains expected headers."""
    engine = AttributionEngine()
    from mock_data import get_mock_backtrack_input
    output = engine.process(get_mock_backtrack_input())
    table_str = engine.render_ascii_table(output)
    assert "ATTRIBUTION ENGINE" in table_str
    assert "MV Ocean Star" in table_str
    assert "MT Gujarat Pearl" in table_str
