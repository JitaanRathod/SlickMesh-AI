"""
test_evidence.py — Unit tests for Phase 2 evidence-field calculations.

These tests run with zero external data — they verify the math in candidate_matcher.py
and backtracker.py against known hand-calculated values.

Run:
  cd phase2-ais-gis
  pytest tests/ -v
"""

import math
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.candidate_matcher import _haversine_nm, _bearing_deg, _angle_diff
from src.backtracker import _compute_drift_vector, _project_point_backward


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

class TestHaversineNm:
    def test_zero_distance(self):
        assert _haversine_nm(20.0, 67.0, 20.0, 67.0) == pytest.approx(0.0, abs=1e-6)

    def test_equator_1_degree_lon(self):
        # 1° of longitude at equator ≈ 60 nm
        dist = _haversine_nm(0.0, 0.0, 0.0, 1.0)
        assert dist == pytest.approx(60.04, abs=0.5)

    def test_spill_to_vessel(self):
        # Spill at (20.48, 67.52), vessel at (20.15, 67.10) — expected ~25–30 nm
        dist = _haversine_nm(20.48, 67.52, 20.15, 67.10)
        assert 20.0 < dist < 35.0

    def test_symmetry(self):
        d1 = _haversine_nm(20.48, 67.52, 19.70, 66.40)
        d2 = _haversine_nm(19.70, 66.40, 20.48, 67.52)
        assert d1 == pytest.approx(d2, rel=1e-9)

    def test_known_arabian_sea_pair(self):
        # Mumbai (18.96, 72.82) → Karachi Port (24.86, 66.99) ≈ 480 nm (haversine)
        dist = _haversine_nm(18.96, 72.82, 24.86, 66.99)
        assert dist == pytest.approx(480, abs=15)


# ---------------------------------------------------------------------------
# Bearing
# ---------------------------------------------------------------------------

class TestBearingDeg:
    def test_due_north(self):
        b = _bearing_deg(0.0, 0.0, 1.0, 0.0)
        assert b == pytest.approx(0.0, abs=0.5)

    def test_due_east(self):
        b = _bearing_deg(0.0, 0.0, 0.0, 1.0)
        assert b == pytest.approx(90.0, abs=0.5)

    def test_due_south(self):
        b = _bearing_deg(1.0, 0.0, 0.0, 0.0)
        assert b == pytest.approx(180.0, abs=0.5)

    def test_due_west(self):
        b = _bearing_deg(0.0, 1.0, 0.0, 0.0)
        assert b == pytest.approx(270.0, abs=0.5)

    def test_northeast_diagonal(self):
        b = _bearing_deg(20.0, 67.0, 21.0, 68.0)
        assert 30.0 < b < 60.0  # roughly NE


# ---------------------------------------------------------------------------
# Angular difference
# ---------------------------------------------------------------------------

class TestAngleDiff:
    def test_same_bearing(self):
        assert _angle_diff(45.0, 45.0) == pytest.approx(0.0)

    def test_opposite_bearings(self):
        assert _angle_diff(0.0, 180.0) == pytest.approx(180.0)

    def test_wraparound(self):
        # 350° and 10° differ by 20°
        assert _angle_diff(350.0, 10.0) == pytest.approx(20.0)

    def test_90_degree_diff(self):
        assert _angle_diff(0.0, 90.0) == pytest.approx(90.0)

    def test_commutative(self):
        assert _angle_diff(30.0, 200.0) == _angle_diff(200.0, 30.0)


# ---------------------------------------------------------------------------
# Drift vector
# ---------------------------------------------------------------------------

class TestDriftVector:
    def _mock_env(self, current_u, current_v, wind_speed, wind_dir):
        return {
            "current_u_ms": current_u,
            "current_v_ms": current_v,
            "wind_speed_ms": wind_speed,
            "wind_direction_deg": wind_dir,
        }

    def test_no_wind_drift_equals_current(self):
        env = self._mock_env(0.18, 0.07, 0.0, 0.0)
        u, v = _compute_drift_vector(env)
        assert u == pytest.approx(0.18)
        assert v == pytest.approx(0.07)

    def test_windage_adds_to_current(self):
        # Wind blowing due East (90°) at 10 m/s — windage adds 0.03 * 10 = 0.3 m/s eastward
        env = self._mock_env(0.0, 0.0, 10.0, 90.0)
        u, v = _compute_drift_vector(env)
        assert u == pytest.approx(0.3, abs=0.01)   # eastward
        assert v == pytest.approx(0.0, abs=0.01)   # no northward component

    def test_mock_env_values(self):
        # Values from mock_env.json
        env = self._mock_env(0.18, 0.07, 5.4, 72.0)
        u, v = _compute_drift_vector(env)
        # drift = current + 0.03 * wind
        wind_rad = math.radians(72.0)
        expected_u = 0.18 + 0.03 * 5.4 * math.sin(wind_rad)
        expected_v = 0.07 + 0.03 * 5.4 * math.cos(wind_rad)
        assert u == pytest.approx(expected_u, rel=1e-6)
        assert v == pytest.approx(expected_v, rel=1e-6)


# ---------------------------------------------------------------------------
# Backtracking projection
# ---------------------------------------------------------------------------

class TestProjectPointBackward:
    def test_zero_drift_stays_at_origin(self):
        lat, lon = _project_point_backward(20.48, 67.52, 0.0, 0.0, 24)
        assert lat == pytest.approx(20.48, abs=1e-4)
        assert lon == pytest.approx(67.52, abs=1e-4)

    def test_eastward_drift_origin_is_west(self):
        # If drift is eastward (+u), the origin (backward projection) should be to the west
        lat, lon = _project_point_backward(20.0, 67.0, drift_u_ms=0.5, drift_v_ms=0.0, hours=10)
        assert lon < 67.0  # origin is west of spill

    def test_northward_drift_origin_is_south(self):
        # If drift is northward (+v), origin should be to the south
        lat, lon = _project_point_backward(20.0, 67.0, drift_u_ms=0.0, drift_v_ms=0.5, hours=10)
        assert lat < 20.0  # origin is south of spill

    def test_distance_scales_with_hours(self):
        lat6, lon6 = _project_point_backward(20.0, 67.0, 0.3, 0.3, 6)
        lat24, lon24 = _project_point_backward(20.0, 67.0, 0.3, 0.3, 24)
        # 24h backtrack should be farther from origin than 6h
        dist6 = math.sqrt((lat6 - 20.0) ** 2 + (lon6 - 67.0) ** 2)
        dist24 = math.sqrt((lat24 - 20.0) ** 2 + (lon24 - 67.0) ** 2)
        assert dist24 > dist6


# ---------------------------------------------------------------------------
# Contract C schema integration test
# ---------------------------------------------------------------------------

class TestContractCSchema:
    """Validate that the mock output passes pydantic validation."""

    def test_mock_passes_validation(self):
        from src.contract_writer import ContractC

        mock = {
            "source_region": {
                "latitude": 20.48,
                "longitude": 67.52,
                "radius_km": 22,
                "backtrack_hours": 24,
            },
            "candidates": [
                {
                    "mmsi": "419001234",
                    "imo": "9123456",
                    "name": "MV Ocean Star",
                    "vessel_type": "Tanker",
                    "position": {"latitude": 20.15, "longitude": 67.10},
                    "track": [[19.70, 66.40], [19.85, 66.70], [20.00, 66.90], [20.15, 67.10]],
                    "evidence": {
                        "min_distance_nm": 3.2,
                        "hours_since_passage": 5.1,
                        "heading_delta_deg": 12,
                        "sog_at_closest_knots": 1.4,
                        "intersects_source_region": True,
                        "track_continuity": "continuous",
                    },
                }
            ],
        }
        validated = ContractC(**mock)
        assert validated.candidates[0].mmsi == "419001234"
        assert validated.candidates[0].evidence.track_continuity == "continuous"

    def test_invalid_track_continuity_raises(self):
        from pydantic import ValidationError
        from src.contract_writer import Evidence

        with pytest.raises(ValidationError):
            Evidence(
                min_distance_nm=1.0,
                hours_since_passage=2.0,
                heading_delta_deg=10,
                sog_at_closest_knots=3.0,
                intersects_source_region=False,
                track_continuity="unknown_value",  # invalid
            )

    def test_invalid_mmsi_raises(self):
        from pydantic import ValidationError
        from src.contract_writer import Candidate, Position, Evidence

        with pytest.raises(ValidationError):
            Candidate(
                mmsi="INVALID_MMSI",
                imo=None,
                name="Test Vessel",
                vessel_type="Tanker",
                position=Position(latitude=20.0, longitude=67.0),
                track=[[20.0, 67.0]],
                evidence=Evidence(
                    min_distance_nm=5.0,
                    hours_since_passage=3.0,
                    heading_delta_deg=None,
                    sog_at_closest_knots=None,
                    intersects_source_region=False,
                    track_continuity="continuous",
                ),
            )
