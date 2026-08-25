"""Pydantic schemas matching Contract C (Input) and Contract D (Output).

Includes defensive parsing, validation, and serialization utilities.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ==========================================
# CONTRACT C: AIS / Backtracking Input Models
# ==========================================

class SourceRegion(BaseModel):
    """Estimated spill origin corridor from hydrodynamic drift backtracking."""
    latitude: float = Field(..., description="Latitude of backtracked source center (deg N)")
    longitude: float = Field(..., description="Longitude of backtracked source center (deg E)")
    radius_km: float = Field(default=20.0, description="Corridor uncertainty radius in km")
    backtrack_hours: float = Field(default=24.0, description="Backtracking simulation window in hours")

    @field_validator("radius_km", mode="before")
    @classmethod
    def sanitize_radius(cls, v: Any) -> float:
        try:
            val = float(v)
            return max(0.1, val)
        except (TypeError, ValueError):
            return 20.0

    @field_validator("backtrack_hours", mode="before")
    @classmethod
    def sanitize_hours(cls, v: Any) -> float:
        try:
            val = float(v)
            return max(0.1, val)
        except (TypeError, ValueError):
            return 24.0


class Position(BaseModel):
    """Vessel geographical position."""
    latitude: float = Field(..., description="Latitude (deg N)")
    longitude: float = Field(..., description="Longitude (deg E)")


class VesselEvidence(BaseModel):
    """Raw physical and kinematic evidence computed by Phase 2 GIS pipeline."""
    min_distance_nm: float = Field(default=0.0, description="Closest point of approach to origin corridor (nautical miles)")
    hours_since_passage: float = Field(default=0.0, description="Time elapsed between vessel CPA and spill detection (hours)")
    heading_delta_deg: float = Field(default=0.0, description="Angular delta between vessel heading and drift vector (deg)")
    sog_at_closest_knots: float = Field(default=0.0, description="Speed Over Ground at closest point (knots)")
    intersects_source_region: bool = Field(default=False, description="True if reconstructed track intersected source circle")
    track_continuity: str = Field(default="continuous", description="'continuous', 'gapped', or 'unknown'")

    @field_validator("min_distance_nm", "hours_since_passage", "sog_at_closest_knots", mode="before")
    @classmethod
    def sanitize_floats(cls, v: Any) -> float:
        try:
            return max(0.0, float(v))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("heading_delta_deg", mode="before")
    @classmethod
    def sanitize_heading(cls, v: Any) -> float:
        try:
            return abs(float(v)) % 360.0
        except (TypeError, ValueError):
            return 0.0

    @field_validator("intersects_source_region", mode="before")
    @classmethod
    def sanitize_bool(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "t")
        return bool(v)

    @field_validator("track_continuity", mode="before")
    @classmethod
    def normalize_continuity(cls, v: Any) -> str:
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ("continuous", "gapped", "unknown"):
                return v_lower
        return "unknown"


class CandidateVessel(BaseModel):
    """A vessel candidate identified near the backtracked source region."""
    mmsi: str = Field(..., description="Maritime Mobile Service Identity")
    imo: Optional[str] = Field(default=None, description="International Maritime Organization number")
    name: str = Field(default="Unknown Vessel", description="Vessel name")
    vessel_type: str = Field(default="Cargo", description="Vessel category (Tanker, Cargo, Tug, etc.)")
    position: Position = Field(..., description="Last known or current position")
    track: List[List[float]] = Field(default_factory=list, description="Reconstructed trajectory as [[lat, lon], ...]")
    evidence: VesselEvidence = Field(default_factory=VesselEvidence, description="Raw GIS/AIS evidence metrics")

    @field_validator("mmsi", mode="before")
    @classmethod
    def sanitize_mmsi(cls, v: Any) -> str:
        return str(v).strip()

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: Any) -> str:
        s = str(v).strip() if v else "Unknown Vessel"
        return s if s else "Unknown Vessel"


class BacktrackInput(BaseModel):
    """Contract C canonical schema: Output from Phase 2 / Input to Phase 3."""
    source_region: SourceRegion
    candidates: List[CandidateVessel] = Field(default_factory=list)


# ==========================================
# CONTRACT D: Attribution Engine Output Models
# ==========================================

class SubScores(BaseModel):
    """Per-feature normalized contribution scores (each in [0.0, 1.0])."""
    environmental_consistency: float = Field(..., ge=0.0, le=1.0)
    distance: float = Field(..., ge=0.0, le=1.0)
    time_consistency: float = Field(..., ge=0.0, le=1.0)
    track_continuity: float = Field(..., ge=0.0, le=1.0)
    heading: float = Field(..., ge=0.0, le=1.0)
    speed: float = Field(..., ge=0.0, le=1.0)
    vessel_type: float = Field(..., ge=0.0, le=1.0)


class RankedVessel(BaseModel):
    """Attributed vessel candidate with confidence, reason, and feature breakdown."""
    mmsi: str
    name: str
    vessel_type: str
    confidence: int = Field(..., ge=0, le=100, description="Overall attribution confidence [0-100]")
    reason: str = Field(..., description="Factual, transparent human-readable explanation")
    sub_scores: SubScores


class AttributionOutput(BaseModel):
    """Contract D canonical schema: Output from Phase 3 to Dashboard / Integration."""
    spill_id: str = Field(default="SPILL-001")
    ranked_vessels: List[RankedVessel] = Field(default_factory=list)

    def to_contract_dict(self) -> Dict[str, Any]:
        """Returns standard dictionary representation matching API_CONTRACTS.md."""
        return self.model_dump()
