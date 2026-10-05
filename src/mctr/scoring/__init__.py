"""Bottom Engine calculations and risk/reward data contracts."""

from typing import Optional, Union

from dataclasses import dataclass

from .bottom import calculate_bottom_engine
from .components import (
    calculate_chip_score,
    calculate_confirmation_factor,
    calculate_exhaustion_score,
    calculate_momentum_reversal_score,
    calculate_position_score,
    calculate_structural_bottom_score,
    calculate_trend_transition_score,
)
from .models import BottomComponentProfile, BottomEngineResult, BottomScoreProfile, RiskOverrideProfile, RiskRewardProfile
from .risk import calculate_contradiction_factor, calculate_risk_override
from .reward import calculate_risk_reward

@dataclass(frozen=True)
class ResistanceZone:
    """A target area rather than a falsely precise target price."""

    lower: float
    upper: float
    label: str
    confidence: Optional[float] = None

@dataclass(frozen=True)
class RiskReward:
    """Risk/reward contract using resistance zones."""

    entry: float
    downside: float
    first_target: ResistanceZone
    second_target: Optional[ResistanceZone] = None
    extreme_target: Optional[ResistanceZone] = None
    ratio: Optional[float] = None

__all__ = [
    "ResistanceZone", "RiskReward", "BottomComponentProfile", "BottomEngineResult",
    "BottomScoreProfile", "RiskOverrideProfile", "RiskRewardProfile",
    "calculate_bottom_engine", "calculate_chip_score", "calculate_confirmation_factor",
    "calculate_contradiction_factor", "calculate_exhaustion_score", "calculate_momentum_reversal_score",
    "calculate_position_score", "calculate_risk_override", "calculate_risk_reward",
    "calculate_structural_bottom_score", "calculate_trend_transition_score",
]
