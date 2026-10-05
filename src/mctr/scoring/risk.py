"""Phase 4 risk override and contradiction calculations."""

from typing import Optional, Union

from collections.abc import Mapping

from mctr.config import BottomConfig
from .models import RiskOverrideProfile

def calculate_contradiction_factor(
    position_score: float,
    momentum_reversal: float,
    chip_score: float,
    market_state: str,
    sector_relative_strength: Optional[float],
    config: BottomConfig,
) -> float:
    """Penalize cheap-but-accelerating-bearish contradictions.

    Low price alone is never rewarded. The factor is based only on current and
    historical features supplied by the caller and remains in [0, 1].
    """

    contradiction = 0.0
    if position_score >= config.contradiction_threshold and momentum_reversal < 0.35:
        contradiction += 0.45
    if chip_score < 0.35:
        contradiction += 0.25
    if market_state in {"M0 Extreme Bear", "M8 Breakdown"}:
        contradiction += 0.35
    if sector_relative_strength is not None and sector_relative_strength < config.weak_sector_relative_strength:
        contradiction += 0.20
    return max(0.0, min(1.0, 1.0 - contradiction))

def calculate_risk_override(
    market_state: str,
    trend_state: str,
    market_gate: float,
    chip_migration: Optional[float],
    momentum_features: Mapping[str, float],
    volume_ratio: Optional[float],
    sector_relative_strength: Optional[float],
    config: BottomConfig,
) -> RiskOverrideProfile:
    """Classify R0-R3 from existing Phase 1/2/3 observations."""
    reasons: list[str] = []
    if market_state in {"M0 Extreme Bear", "M8 Breakdown"} or market_gate <= 0.0:
        reasons.append("systemic market risk")
    if trend_state == "T6_TREND_BROKEN":
        reasons.append("trend broken")
    if chip_migration is not None and chip_migration < -config.price_window_pct:
        reasons.append("chip peak moving rapidly downward")
    histogram_slope = momentum_features.get("histogram_slope", momentum_features.get("slope", 0.0))
    if histogram_slope < config.bearish_momentum_threshold:
        reasons.append("MACD histogram bearish acceleration")
    if volume_ratio is not None and volume_ratio >= config.extreme_volume_ratio and momentum_features.get("price_velocity", 0.0) < 0.0:
        reasons.append("high volume with adverse price movement")
    if sector_relative_strength is not None and sector_relative_strength < config.weak_sector_relative_strength:
        reasons.append("sector persistently weaker than market")
    if market_state in {"M2 Decline Exhaustion", "M7 Bull Exhaustion"}:
        reasons.append("market exhaustion state")
    if market_state in {"M0 Extreme Bear", "M8 Breakdown"}:
        state, factor = "R3", config.risk_r3_factor
    elif trend_state == "T6_TREND_BROKEN" or len(reasons) >= 2:
        state, factor = "R2", config.risk_r2_factor
    elif reasons:
        state, factor = "R1", config.risk_r1_factor
    else:
        state, factor = "R0", 1.0
    return RiskOverrideProfile(state, factor, tuple(reasons), "high" if state == "R0" else "medium")
