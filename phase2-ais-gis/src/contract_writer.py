"""
contract_writer.py — Validate and write Contract C JSON (Phase 2 → Phase 3 handoff).

Uses pydantic models mirroring the exact schema in API_CONTRACTS.md §C.
A schema validation failure raises at runtime — catches drift before demo time.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

from src.config import CONTRACT_C_FILE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models — mirror of Contract C schema
# ---------------------------------------------------------------------------

class SourceRegion(BaseModel):
    latitude: float
    longitude: float
    radius_km: float
    backtrack_hours: int


class Position(BaseModel):
    latitude: float
    longitude: float


class Evidence(BaseModel):
    min_distance_nm: float
    hours_since_passage: float
    heading_delta_deg: Optional[float]
    sog_at_closest_knots: Optional[float]
    intersects_source_region: bool
    track_continuity: str  # "continuous" | "gapped"

    @field_validator("track_continuity")
    @classmethod
    def continuity_values(cls, v: str) -> str:
        allowed = {"continuous", "gapped"}
        if v not in allowed:
            raise ValueError(f"track_continuity must be one of {allowed}, got '{v}'")
        return v


class Candidate(BaseModel):
    mmsi: str
    imo: Optional[str]
    name: str
    vessel_type: str
    position: Position
    track: list[list[float]]  # list of [lat, lon] pairs
    evidence: Evidence

    @field_validator("track")
    @classmethod
    def track_pairs(cls, v: list) -> list:
        for pair in v:
            if len(pair) != 2:
                raise ValueError(f"Each track point must be [lat, lon], got {pair}")
        return v

    @field_validator("mmsi")
    @classmethod
    def mmsi_format(cls, v: str) -> str:
        if not v.isdigit() or not (7 <= len(v) <= 9):
            raise ValueError(f"MMSI '{v}' does not look like a valid 7–9 digit MMSI")
        return v


class ContractC(BaseModel):
    source_region: SourceRegion
    candidates: list[Candidate]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_and_write(
    source_region: dict,
    candidates: list[dict],
    output_path: Path = CONTRACT_C_FILE,
) -> dict:
    """
    Validate against Contract C schema and write `output/contract_c.json`.

    Parameters
    ----------
    source_region : dict — output of backtracker.compute_origin_corridor()
                           (only the Contract C keys are used; internal keys are stripped)
    candidates : list[dict] — output of candidate_matcher.match_candidates()
    output_path : Path — where to write the JSON (default: config.CONTRACT_C_FILE)

    Returns
    -------
    dict — the validated, serialisable Contract C payload

    Raises
    ------
    pydantic.ValidationError — if the data doesn't conform to Contract C schema
    """
    # Strip internal backtracker keys not part of the contract
    sr_clean = {
        "latitude": source_region["latitude"],
        "longitude": source_region["longitude"],
        "radius_km": source_region["radius_km"],
        "backtrack_hours": source_region["backtrack_hours"],
    }

    payload = {"source_region": sr_clean, "candidates": candidates}

    # Validate — will raise pydantic.ValidationError if schema is violated
    validated = ContractC(**payload)
    output = validated.model_dump()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    logger.info("Contract C written to %s (%d candidates)", output_path, len(candidates))
    return output
