"""
Phase 1 Data Contracts — Pydantic models for Contract A (Satellite Detection Output).
Ref: API_CONTRACTS.md §A and phase1-satellite-detection.md §7
"""

from enum import Enum
from typing import List
from pydantic import BaseModel, Field, field_validator


class QualityFlagEnum(str, Enum):
    FAVORABLE = "favorable"
    LOW_WIND_RISK = "low_wind_risk"
    HIGH_WIND_RISK = "high_wind_risk"
    UNRELIABLE = "unreliable"


class Centroid(BaseModel):
    """Centroid of detected slick using explicit lat/lon key names."""
    lat: float = Field(..., description="Latitude in decimal degrees", ge=-90.0, le=90.0)
    lon: float = Field(..., description="Longitude in decimal degrees", ge=-180.0, le=180.0)


class SatelliteDetectionOutput(BaseModel):
    """
    Contract A: Satellite Detection Output schema.
    Coordinate order note: `polygon` uses [lon, lat] pairs (GeoJSON order).
    """
    spill_id: str = Field(..., description="Unique slick identifier")
    detected_at: str = Field(..., description="ISO 8601 acquisition timestamp")
    spill_detected: bool = Field(..., description="Flag indicating slick detection")
    confidence: float = Field(..., description="Model probability (0.0 to 1.0)", ge=0.0, le=1.0)
    area_km2: float = Field(..., description="Estimated slick surface area in sq km", ge=0.0)
    centroid: Centroid = Field(..., description="Slick centroid coordinate")
    polygon: List[List[float]] = Field(
        ...,
        description="Bounding/contour polygon coordinates in GeoJSON [lon, lat] order"
    )
    quality_flag: QualityFlagEnum = Field(..., description="Operational quality flag derived from wind conditions")
    notes: str = Field(
        default="candidate detection — not chemically confirmed",
        description="Disclaimer / contextual notes"
    )

    @field_validator("polygon")
    @classmethod
    def validate_polygon_coords(cls, v: List[List[float]]) -> List[List[float]]:
        if not v:
            return v
        for pt in v:
            if len(pt) != 2:
                raise ValueError(f"Each polygon point must be a [lon, lat] pair of length 2, got: {pt}")
            lon, lat = pt[0], pt[1]
            if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                raise ValueError(f"Invalid coordinate values in polygon: lon={lon}, lat={lat}")
        return v


def get_mock_contract_a() -> SatelliteDetectionOutput:
    """Returns the canonical reference Contract A payload from API_CONTRACTS.md."""
    return SatelliteDetectionOutput(
        spill_id="SPILL-001",
        detected_at="2026-08-25T06:00:00Z",
        spill_detected=True,
        confidence=0.87,
        area_km2=3.2,
        centroid=Centroid(lat=20.48, lon=67.52),
        polygon=[
            [67.15, 20.45],
            [67.45, 20.75],
            [67.90, 20.62],
            [67.70, 20.30],
            [67.35, 20.25]
        ],
        quality_flag=QualityFlagEnum.FAVORABLE,
        notes="candidate detection — not chemically confirmed"
    )
