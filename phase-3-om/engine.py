"""Core Attribution Engine for SIH26143.

Fuses physical, spatial, temporal, and AIS kinematic evidence to produce an
explainable 0-100 confidence ranking per candidate vessel.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any, Union
import json
import math
from pathlib import Path

try:
    from .models import (
        BacktrackInput,
        CandidateVessel,
        SourceRegion,
        SubScores,
        RankedVessel,
        AttributionOutput
    )
    from .normalizers import compute_all_subscores
    from .explainer import generate_reason_string, get_feature_drivers
except ImportError:
    from models import (
        BacktrackInput,
        CandidateVessel,
        SourceRegion,
        SubScores,
        RankedVessel,
        AttributionOutput
    )
    from normalizers import compute_all_subscores
    from explainer import generate_reason_string, get_feature_drivers


@dataclass
class AttributionWeights:
    """Configurable weights for the multi-evidence linear scoring model."""
    environmental_consistency: float = 0.25
    distance: float = 0.20
    time_consistency: float = 0.20
    track_continuity: float = 0.15
    heading: float = 0.10
    speed: float = 0.05
    vessel_type: float = 0.05

    def __post_init__(self):
        self.validate()

    def validate(self):
        total = (
            self.environmental_consistency +
            self.distance +
            self.time_consistency +
            self.track_continuity +
            self.heading +
            self.speed +
            self.vessel_type
        )
        if not math.isclose(total, 1.0, rel_tol=1e-3):
            raise ValueError(f"Attribution weights must sum to 1.0, got {total:.4f}")

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


class AttributionEngine:
    """Computes explainable vessel attribution rankings from GIS backtrack candidates."""

    def __init__(self, weights: Optional[AttributionWeights] = None):
        self.weights = weights or AttributionWeights()
        self.weights.validate()

    def score_vessel_weighted(
        self,
        candidate: CandidateVessel,
        source_region: SourceRegion
    ) -> RankedVessel:
        """Evaluates a single vessel using the transparent weighted linear model."""
        sub_scores_dict = compute_all_subscores(
            candidate.evidence,
            source_region,
            candidate.vessel_type
        )

        w = self.weights
        raw_score = (
            w.environmental_consistency * sub_scores_dict["environmental_consistency"] +
            w.distance * sub_scores_dict["distance"] +
            w.time_consistency * sub_scores_dict["time_consistency"] +
            w.track_continuity * sub_scores_dict["track_continuity"] +
            w.heading * sub_scores_dict["heading"] +
            w.speed * sub_scores_dict["speed"] +
            w.vessel_type * sub_scores_dict["vessel_type"]
        )

        confidence = int(round(max(0.0, min(100.0, raw_score * 100.0))))

        reason = generate_reason_string(
            candidate.name,
            candidate.vessel_type,
            candidate.evidence,
            source_region,
            sub_scores_dict
        )

        return RankedVessel(
            mmsi=candidate.mmsi,
            name=candidate.name,
            vessel_type=candidate.vessel_type,
            confidence=confidence,
            reason=reason,
            sub_scores=SubScores(**sub_scores_dict)
        )

    def score_vessels_bayesian(
        self,
        candidates: List[CandidateVessel],
        source_region: SourceRegion
    ) -> List[RankedVessel]:
        """Stretch method: computes relative posterior attribution probabilities via Bayesian update."""
        if not candidates:
            return []

        likelihoods = []
        sub_scores_list = []
        for c in candidates:
            sub_dict = compute_all_subscores(c.evidence, source_region, c.vessel_type)
            sub_scores_list.append(sub_dict)
            
            prior = 0.50 if "tanker" in c.vessel_type.lower() else (0.35 if "cargo" in c.vessel_type.lower() else 0.15)
            
            l_env = max(0.05, sub_dict["environmental_consistency"])
            l_dist = max(0.05, sub_dict["distance"])
            l_time = max(0.05, sub_dict["time_consistency"])
            l_cont = max(0.05, sub_dict["track_continuity"])
            l_head = max(0.05, sub_dict["heading"])
            
            unnormalized_posterior = prior * (l_env ** 1.5) * (l_dist ** 1.2) * (l_time ** 1.2) * (l_cont ** 0.8) * (l_head ** 0.5)
            likelihoods.append(unnormalized_posterior)

        total_posterior = sum(likelihoods)
        results = []
        for i, c in enumerate(candidates):
            sub_dict = sub_scores_list[i]
            post_prob = (likelihoods[i] / total_posterior) if total_posterior > 0 else 0.0
            confidence = int(round(max(0.0, min(100.0, post_prob * 100.0))))
            reason = generate_reason_string(c.name, c.vessel_type, c.evidence, source_region, sub_dict)
            results.append(RankedVessel(
                mmsi=c.mmsi,
                name=c.name,
                vessel_type=c.vessel_type,
                confidence=confidence,
                reason=reason,
                sub_scores=SubScores(**sub_dict)
            ))

        return results

    def process(
        self,
        input_data: Union[BacktrackInput, Dict[str, Any], str, Path],
        spill_id: str = "SPILL-001",
        method: str = "weighted"
    ) -> AttributionOutput:
        """Processes Contract C input into sorted Contract D output.

        Accepts a BacktrackInput model, raw dictionary, JSON string, or file path.
        """
        if isinstance(input_data, (str, Path)):
            p = Path(str(input_data))
            if p.exists() and p.is_file():
                with open(p, "r", encoding="utf-8") as f:
                    raw_dict = json.load(f)
            else:
                raw_dict = json.loads(str(input_data))
            backtrack_input = BacktrackInput.model_validate(raw_dict)
        elif isinstance(input_data, dict):
            backtrack_input = BacktrackInput.model_validate(input_data)
        elif isinstance(input_data, BacktrackInput):
            backtrack_input = input_data
        else:
            raise ValueError(f"Unsupported input type for attribution engine: {type(input_data)}")

        if method.lower() == "bayesian":
            ranked = self.score_vessels_bayesian(
                backtrack_input.candidates,
                backtrack_input.source_region
            )
        else:
            ranked = [
                self.score_vessel_weighted(c, backtrack_input.source_region)
                for c in backtrack_input.candidates
            ]

        # Output MUST be pre-sorted descending by confidence as per Contract D
        ranked.sort(key=lambda v: v.confidence, reverse=True)

        return AttributionOutput(
            spill_id=spill_id,
            ranked_vessels=ranked
        )

    def render_ascii_table(self, output: AttributionOutput) -> str:
        """Renders an ASCII summary table of ranked attribution results for presentations."""
        lines = []
        lines.append("=" * 95)
        lines.append(f" SIH26143 ATTRIBUTION ENGINE - INCIDENT REPORT [{output.spill_id}]")
        lines.append("=" * 95)
        lines.append(f"{'RANK':<5} | {'CONF':<6} | {'NAME':<18} | {'TYPE':<9} | {'MMSI':<11} | {'KEY REASON':<36}")
        lines.append("-" * 95)
        
        if not output.ranked_vessels:
            lines.append("  No candidate vessels identified in surveillance area.")
        else:
            for i, v in enumerate(output.ranked_vessels, 1):
                reason_trunc = (v.reason[:33] + "...") if len(v.reason) > 36 else v.reason
                lines.append(f"#{i:<4} | {v.confidence:>3}%  | {v.name:<18} | {v.vessel_type:<9} | {v.mmsi:<11} | {reason_trunc:<36}")
        
        lines.append("=" * 95)
        lines.append(" * Note: Probabilistic attribution triage for investigative prioritization; not legal proof.")
        lines.append("=" * 95)
        return "\n".join(lines)
