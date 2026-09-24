"""
SIH26143 SlickMesh-AI — Master End-to-End Integration Test Suite.
Verifies complete pipeline execution across Phase 1 (Detection), Phase 2 (AIS Backtracking),
Phase 3 (Attribution Engine), and Phase 4 (Contract E Integration & GeoJSON Assembly).
"""

import os
import sys
import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "phase3-attribution"))
sys.path.insert(0, str(ROOT_DIR / "phase2-ais-gis"))
sys.path.insert(0, str(ROOT_DIR / "phase1-satellite"))
sys.path.insert(0, str(ROOT_DIR))

from run_pipeline import run_master_pipeline, get_scenario_data
from server import execute_integrated_pipeline, app
from fastapi.testclient import TestClient


@pytest.fixture
def api_client():
    return TestClient(app)


def test_master_pipeline_execution_all_scenarios():
    """Verify master pipeline runs without error across all 4 regional scenarios."""
    scenarios = ["alang", "mumbai", "kg_basin", "dark_ship"]
    for sc in scenarios:
        output_file = ROOT_DIR / "dashboard" / f"incident_{sc}.json"
        result = run_master_pipeline(
            scenario=sc,
            wind_speed=5.4,
            backtrack_hours=24,
            output_path=str(output_file),
            show_table=False
        )

        assert "incident" in result
        assert "environment" in result
        assert "source_region" in result
        assert "vessels" in result

        incident = result["incident"]
        assert incident["id"].startswith("SPILL-")
        assert incident["area_km2"] > 0
        assert 0.0 <= incident["confidence"] <= 1.0
        assert len(incident["polygon"]) >= 3

        vessels = result["vessels"]
        assert len(vessels) >= 1

        # Check ranking order (descending confidence)
        confidences = [v["confidence"] for v in vessels]
        assert confidences == sorted(confidences, reverse=True)

        # Check GeoJSON formatting
        for v in vessels:
            assert isinstance(v["position"], list) and len(v["position"]) == 2
            assert isinstance(v["track"], list) and len(v["track"]) >= 1
            assert len(v["reason"]) > 10
            assert "sub_scores" in v
            for metric in [
                "environmental_consistency", "distance", "time_consistency",
                "track_continuity", "heading", "speed", "vessel_type"
            ]:
                assert metric in v["sub_scores"]
                assert 0.0 <= v["sub_scores"][metric] <= 1.0


def test_fastapi_server_endpoints(api_client):
    """Verify FastAPI integration server endpoints."""
    # Test GET /api/mock-incident
    res = api_client.get("/api/mock-incident")
    assert res.status_code == 200
    data = res.json()
    assert "incident" in data
    assert "vessels" in data

    # Test POST /api/run-pipeline with Mumbai preset
    payload = {
        "image_name": "s1_active.png",
        "wind_speed": 6.2,
        "wind_direction": 240.0,
        "current_u": 0.12,
        "current_v": -0.15,
        "backtrack_hours": 18,
        "target_region": "mumbai"
    }
    res_post = api_client.post("/api/run-pipeline", json=payload)
    assert res_post.status_code == 200
    post_data = res_post.json()
    assert post_data["incident"]["confidence"] > 0.8
    assert len(post_data["vessels"]) >= 2
    assert post_data["vessels"][0]["name"] == "Al-Bahar Crude"
    assert post_data["vessels"][0]["confidence"] >= 80

    # Verify Confidence Decomposition
    assert "confidence_decomposition" in post_data["incident"]
    cd = post_data["incident"]["confidence_decomposition"]
    assert "detection_confidence" in cd
    assert "origin_confidence" in cd
    assert "attribution_evidence_index" in cd

    # Verify 4-Stage Filtering Funnel
    assert "filtering_funnel" in post_data
    fun = post_data["filtering_funnel"]
    assert fun["fleet_in_basin"] >= 400
    assert fun["spatial_intersect_corridor"] > 0
    assert fun["temporal_window_aligned"] > 0
    assert fun["scored_candidates"] > 0

    # Verify Observed vs Reconstructed Validation
    assert "validation" in post_data
    val = post_data["validation"]
    assert val["iou_score"] >= 0.70
    assert val["centroid_error_km"] <= 3.0

    # Verify Forensic Timeline Frames
    assert "timeline_frames" in post_data
    assert len(post_data["timeline_frames"]) >= 5


def test_investigation_report_generation(api_client):
    """Verify official 17-point investigation report endpoint."""
    payload = {
        "image_name": "s1_active.png",
        "wind_speed": 5.4,
        "wind_direction": 72.0,
        "current_u": 0.18,
        "current_v": 0.07,
        "backtrack_hours": 24,
        "target_region": "mumbai"
    }
    res = api_client.post("/api/generate-report", json=payload)
    assert res.status_code == 200
    report_data = res.json()
    assert "report_id" in report_data
    assert "markdown" in report_data
    md = report_data["markdown"]
    assert "SLICKMESH MARITIME INVESTIGATION BRIEF" in md
    assert "SATELLITE RADAR OBSERVATION" in md
    assert "METOCEAN HYDRODYNAMICS" in md
    assert "FILTERING FUNNEL" in md
    assert "OBSERVED VS RECONSTRUCTED VALIDATION" in md
    assert "STATUTORY & REGULATORY DISCLAIMER" in md


def test_contract_compatibility_fidelity():
    """Verify that Contract E generated on disk matches contract standard."""
    contract_e_path = ROOT_DIR / "dashboard" / "incident.json"
    assert contract_e_path.exists()

    with open(contract_e_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Check top-level keys
    for req_key in ["incident", "environment", "source_region", "vessels"]:
        assert req_key in payload

    # Source region radius is positive
    assert payload["source_region"]["radius_km"] > 0
    assert payload["source_region"]["backtrack_hours"] > 0


def test_gis_layers_and_dense_fleet(api_client):
    """Verify GIS layers (TSS, EEZ boundary, Offshore infrastructure) and high-density fleet."""
    res = api_client.get("/api/gis-layers")
    assert res.status_code == 200
    gis_data = res.json()

    assert "tss_lanes" in gis_data
    assert len(gis_data["tss_lanes"]["features"]) >= 4
    assert "eez_boundary" in gis_data
    assert len(gis_data["eez_boundary"]["features"]) >= 1
    assert "oil_infrastructure" in gis_data
    assert len(gis_data["oil_infrastructure"]["features"]) >= 5
    assert gis_data["vessel_count"] >= 30

    # Verify live fleet endpoint
    res_fleet = api_client.get("/api/live-fleet")
    assert res_fleet.status_code == 200
    fleet_data = res_fleet.json()
    assert fleet_data["count"] >= 30
    assert len(fleet_data["vessels"]) >= 30

    # Verify sweep endpoint returns active SAR alerts and clean swaths
    res_sweep = api_client.get("/api/sweep-eez")
    assert res_sweep.status_code == 200
    sweep_data = res_sweep.json()
    assert "swaths" in sweep_data
    assert len(sweep_data["swaths"]) >= 8
    assert sweep_data["summary"]["active_alerts_detected"] >= 1
    assert sweep_data["summary"]["total_live_vessels_tracked"] >= 30


