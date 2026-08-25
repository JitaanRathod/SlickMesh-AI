"""Unit tests for individual feature normalizers."""

import pytest
from normalizers import (
    normalize_environmental_consistency,
    normalize_distance,
    normalize_time,
    normalize_heading,
    normalize_speed,
    normalize_vessel_type,
    normalize_continuity
)


def test_normalize_environmental_consistency():
    # True intersection inside corridor should produce high consistency (>= 0.8)
    score_inside = normalize_environmental_consistency(True, 3.2, 22.0)
    assert 0.8 <= score_inside <= 1.0

    # Outside corridor with large distance should be penalized (< 0.5)
    score_outside = normalize_environmental_consistency(False, 14.6, 22.0)
    assert 0.0 <= score_outside <= 0.4


def test_normalize_distance():
    # 0 distance -> 1.0
    assert normalize_distance(0.0, 22.0) == 1.0
    # Far distance beyond corridor buffer -> 0.0
    assert normalize_distance(50.0, 22.0) == 0.0
    # Intermediate distance is bounded
    score = normalize_distance(3.2, 22.0)
    assert 0.0 < score < 1.0


def test_normalize_time():
    # 0 hours elapsed -> 1.0
    assert normalize_time(0.0, 24.0) == 1.0
    # Beyond simulation window -> 0.0
    assert normalize_time(30.0, 24.0) == 0.0
    # Intermediate hours
    score = normalize_time(5.1, 24.0)
    assert 0.0 < score < 1.0


def test_normalize_heading():
    # 0 deg delta (parallel to drift) -> 1.0
    assert normalize_heading(0.0) == 1.0
    # 180 deg delta (opposite direction) -> 0.0
    assert normalize_heading(180.0) == 0.0
    # 360 deg wraps to 0 -> 1.0
    assert normalize_heading(360.0) == 1.0
    # Intermediate angle
    assert 0.0 < normalize_heading(45.0) < 1.0


def test_normalize_speed():
    # Low speed (loitering) gets higher likelihood
    assert normalize_speed(1.4) == 0.90
    # High cruise speed gets lower likelihood
    assert normalize_speed(22.0) == 0.30


def test_normalize_vessel_type():
    assert normalize_vessel_type("Crude Oil Tanker") == 1.0
    assert normalize_vessel_type("Container Ship") == 0.70
    assert normalize_vessel_type("Fishing Vessel") == 0.40
    # Never drops to zero (non-tankers carry bunker fuel)
    assert normalize_vessel_type("Yacht") > 0.0


def test_normalize_continuity():
    assert normalize_continuity("continuous") == 0.90
    assert normalize_continuity("gapped") == 0.40
    assert normalize_continuity("unknown") == 0.50
