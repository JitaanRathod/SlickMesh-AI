"""
Wind Quality Flag Evaluator — Physics-based operational wind speed flag.
Ref: phase1-satellite-detection.md §6
"""

from typing import Optional
from contracts import QualityFlagEnum


def evaluate_wind_quality_flag(wind_speed_ms: Optional[float] = None) -> QualityFlagEnum:
    """
    Evaluates SAR oil slick detection reliability based on surface wind speed (m/s).

    Rough operational regimes:
    - < 3.0 m/s: Sea too smooth (low capillary wave scatter, dark look-alikes dominate) -> 'unreliable'
    - 3.0 - 10.0 m/s: Optimal contrast regime -> 'favorable'
    - 10.0 - 15.0 m/s: Moderate wind mixing / damping breakdown -> 'high_wind_risk'
    - > 15.0 m/s: Sea too rough (oil slick dispersed / radar contrast lost) -> 'unreliable'
    """
    if wind_speed_ms is None:
        # Default fallback if wind speed feed is unavailable
        return QualityFlagEnum.FAVORABLE

    if wind_speed_ms < 3.0:
        return QualityFlagEnum.UNRELIABLE
    elif 3.0 <= wind_speed_ms <= 10.0:
        return QualityFlagEnum.FAVORABLE
    elif 10.0 < wind_speed_ms <= 15.0:
        return QualityFlagEnum.HIGH_WIND_RISK
    else:  # > 15.0 m/s
        return QualityFlagEnum.UNRELIABLE
