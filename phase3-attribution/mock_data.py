"""Canonical mock data fixtures for Contract C and Contract D."""

try:
    from .models import BacktrackInput, AttributionOutput
except ImportError:
    from models import BacktrackInput, AttributionOutput

MOCK_CONTRACT_C_DATA = {
    "source_region": {
        "latitude": 20.48,
        "longitude": 67.52,
        "radius_km": 22.0,
        "backtrack_hours": 24.0
    },
    "candidates": [
        {
            "mmsi": "419001234",
            "imo": "9123456",
            "name": "MV Ocean Star",
            "vessel_type": "Tanker",
            "position": {
                "latitude": 20.15,
                "longitude": 67.10
            },
            "track": [
                [19.70, 66.40],
                [19.85, 66.70],
                [20.00, 66.90],
                [20.15, 67.10]
            ],
            "evidence": {
                "min_distance_nm": 3.2,
                "hours_since_passage": 5.1,
                "heading_delta_deg": 12.0,
                "sog_at_closest_knots": 1.4,
                "intersects_source_region": True,
                "track_continuity": "continuous"
            }
        },
        {
            "mmsi": "419005678",
            "imo": "9007654",
            "name": "MT Gujarat Pearl",
            "vessel_type": "Cargo",
            "position": {
                "latitude": 21.10,
                "longitude": 67.70
            },
            "track": [
                [21.40, 67.20],
                [21.30, 67.35],
                [21.20, 67.55],
                [21.10, 67.70]
            ],
            "evidence": {
                "min_distance_nm": 14.6,
                "hours_since_passage": 9.8,
                "heading_delta_deg": 41.0,
                "sog_at_closest_knots": 9.2,
                "intersects_source_region": False,
                "track_continuity": "gapped"
            }
        }
    ]
}

MOCK_CONTRACT_D_DATA = {
    "spill_id": "SPILL-001",
    "ranked_vessels": [
        {
            "mmsi": "419001234",
            "name": "MV Ocean Star",
            "vessel_type": "Tanker",
            "confidence": 79,
            "reason": "Passed within 3.2 nm of the backtracked source region 5.1 hours before detection.",
            "sub_scores": {
                "environmental_consistency": 0.9,
                "distance": 0.85,
                "time_consistency": 0.7,
                "track_continuity": 0.8,
                "heading": 0.75,
                "speed": 0.6,
                "vessel_type": 1.0
            }
        }
    ]
}


def get_mock_backtrack_input() -> BacktrackInput:
    """Returns parsed Pydantic model of the canonical Contract C mock input."""
    return BacktrackInput.model_validate(MOCK_CONTRACT_C_DATA)


def get_mock_attribution_output() -> AttributionOutput:
    """Returns parsed Pydantic model of the canonical Contract D mock output."""
    return AttributionOutput.model_validate(MOCK_CONTRACT_D_DATA)
