"""Realistic benchmark scenarios for SIH26143 Attribution Engine.

Models diverse real-world maritime conditions in the Arabian Sea / Bay of Bengal:
1. Canonical 2-vessel baseline
2. Dense multi-vessel shipping lane (Mumbai High / Gulf of Khambhat)
3. AIS gap / Dark vessel anomaly
4. Multi-tanker timing resolution scenario
"""

from typing import Dict, Any

SCENARIO_CANONICAL: Dict[str, Any] = {
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
            "position": {"latitude": 20.15, "longitude": 67.10},
            "track": [[19.70, 66.40], [19.85, 66.70], [20.00, 66.90], [20.15, 67.10]],
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
            "position": {"latitude": 21.10, "longitude": 67.70},
            "track": [[21.40, 67.20], [21.30, 67.35], [21.20, 67.55], [21.10, 67.70]],
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

SCENARIO_DENSE_TRAFFIC: Dict[str, Any] = {
    "source_region": {
        "latitude": 19.12,
        "longitude": 71.85,
        "radius_km": 25.0,
        "backtrack_hours": 36.0
    },
    "candidates": [
        {
            "mmsi": "419000101",
            "name": "Al-Bahar Crude",
            "vessel_type": "Crude Oil Tanker",
            "position": {"latitude": 19.10, "longitude": 71.80},
            "track": [[18.90, 71.60], [19.00, 71.70], [19.10, 71.80]],
            "evidence": {
                "min_distance_nm": 1.8,
                "hours_since_passage": 3.2,
                "heading_delta_deg": 8.0,
                "sog_at_closest_knots": 2.1,
                "intersects_source_region": True,
                "track_continuity": "continuous"
            }
        },
        {
            "mmsi": "419000102",
            "name": "Bharat Pioneer",
            "vessel_type": "Product Tanker",
            "position": {"latitude": 19.25, "longitude": 71.95},
            "track": [[19.10, 71.75], [19.25, 71.95]],
            "evidence": {
                "min_distance_nm": 4.5,
                "hours_since_passage": 7.0,
                "heading_delta_deg": 22.0,
                "sog_at_closest_knots": 11.4,
                "intersects_source_region": True,
                "track_continuity": "continuous"
            }
        },
        {
            "mmsi": "419000103",
            "name": "Ever Fortune",
            "vessel_type": "Container Ship",
            "position": {"latitude": 19.40, "longitude": 72.10},
            "track": [[19.30, 71.90], [19.40, 72.10]],
            "evidence": {
                "min_distance_nm": 11.2,
                "hours_since_passage": 14.5,
                "heading_delta_deg": 35.0,
                "sog_at_closest_knots": 18.2,
                "intersects_source_region": False,
                "track_continuity": "continuous"
            }
        },
        {
            "mmsi": "419000104",
            "name": "Sindhu Shrestha",
            "vessel_type": "Offshore Supply Vessel",
            "position": {"latitude": 19.05, "longitude": 71.70},
            "track": [[19.00, 71.65], [19.05, 71.70]],
            "evidence": {
                "min_distance_nm": 5.8,
                "hours_since_passage": 6.2,
                "heading_delta_deg": 15.0,
                "sog_at_closest_knots": 4.5,
                "intersects_source_region": True,
                "track_continuity": "continuous"
            }
        },
        {
            "mmsi": "419000105",
            "name": "Matsya Sagar",
            "vessel_type": "Fishing Trawler",
            "position": {"latitude": 18.95, "longitude": 71.60},
            "track": [[18.90, 71.55], [18.95, 71.60]],
            "evidence": {
                "min_distance_nm": 8.1,
                "hours_since_passage": 18.0,
                "heading_delta_deg": 65.0,
                "sog_at_closest_knots": 3.8,
                "intersects_source_region": False,
                "track_continuity": "gapped"
            }
        }
    ]
}

SCENARIO_AIS_SPOOFING_GAP: Dict[str, Any] = {
    "source_region": {
        "latitude": 17.50,
        "longitude": 72.20,
        "radius_km": 20.0,
        "backtrack_hours": 24.0
    },
    "candidates": [
        {
            "mmsi": "419099999",
            "name": "Shadow Trader",
            "vessel_type": "Chemical Tanker",
            "position": {"latitude": 17.65, "longitude": 72.35},
            "track": [[17.30, 72.00], [17.65, 72.35]],
            "evidence": {
                "min_distance_nm": 2.1,
                "hours_since_passage": 4.0,
                "heading_delta_deg": 10.0,
                "sog_at_closest_knots": 1.2,
                "intersects_source_region": True,
                "track_continuity": "gapped"  # Critical signal: AIS blackout during transit
            }
        },
        {
            "mmsi": "419088888",
            "name": "Kolkata Express",
            "vessel_type": "Bulk Carrier",
            "position": {"latitude": 17.80, "longitude": 72.50},
            "track": [[17.20, 71.90], [17.80, 72.50]],
            "evidence": {
                "min_distance_nm": 16.5,
                "hours_since_passage": 12.0,
                "heading_delta_deg": 55.0,
                "sog_at_closest_knots": 13.0,
                "intersects_source_region": False,
                "track_continuity": "continuous"
            }
        }
    ]
}
