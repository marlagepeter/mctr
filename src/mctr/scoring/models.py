"""Phase 4 Bottom Engine result models."""

from typing import Literal, Optional, Union

from dataclasses import dataclass

@dataclass(frozen=True)
class BottomComponentProfile:
    """Raw component scores before structural aggregation."""

    position_score: float
    chip_score: float
    exhaustion_score: float
    momentum_reversal_score: float
    trend_transition_score: float
    resonance_score: float
    position_reason: str
    chip_reason: str
    exhaustion_reason: str
    momentum_reason: str
    trend_reason: str
    resonance_reason: str
    confidence: str

@dataclass(frozen=True)
class RiskOverrideProfile:
    """Explicit risk veto state, separate from bottom structure."""

    state: Literal["R0", "R1", "R2", "R3"]
    risk_factor: float
    reasons: tuple[str, ...]
    confidence: str

@dataclass(frozen=True)
class RiskRewardProfile:
    """Current-observation risk/reward zones, never a price forecast."""

    entry: float
    downside_risk_zone: Optional[tuple[float, float]]
    target_zone_1: Optional[tuple[float, float]]
    target_zone_2: Optional[tuple[float, float]]
    extreme_target_zone: Optional[tuple[float, float]]
    rr1: Optional[float]
    rr2: Optional[float]
    rr_extreme: Optional[float]
    confidence: str
    explanation: str

@dataclass(frozen=True)
class BottomScoreProfile:
    """Separated structural score, confirmation, contradiction and risk."""

    structural_bottom_score: float
    confirmation_factor: float
    contradiction_factor: float
    risk_factor: float
    bottom_probability: float

@dataclass(frozen=True)
class BottomEngineResult:
    """Complete explainable point-in-time Bottom Engine output."""

    as_of_date: object
    position_score: float
    chip_score: float
    exhaustion_score: float
    momentum_reversal_score: float
    trend_transition_score: float
    resonance_score: float
    structural_bottom_score: float
    confirmation_factor: float
    contradiction_factor: float
    risk_factor: float
    bottom_probability: float
    bottom_level: str
    risk_override_state: str
    risk_override_reasons: tuple[str, ...]
    risk_reward: RiskRewardProfile
    explanation: dict[str, str]
    confidence: str
