"""Configuration primitives for point-in-time research features."""

from typing import Mapping

from dataclasses import dataclass
from types import MappingProxyType

DEFAULT_ACTIVITY_WEIGHTS: Mapping[str, float] = MappingProxyType({
    "retail": 0.85,
    "institution": 0.45,
    "fund": 0.55,
    "insurance": 0.25,
    "social_security": 0.20,
    "company": 0.20,
    "controller": 0.10,
    "executive": 0.15,
    "strategic": 0.10,
    "unknown": 0.35,
})

@dataclass(frozen=True)
class ChipConfig:
    """Uncalibrated V1 priors and windows for the chip engine."""

    activity_weights: Mapping[str, float] = DEFAULT_ACTIVITY_WEIGHTS
    unknown_activity_weight: float = 0.35
    known_coverage_confidence_threshold: float = 0.80
    core_coverage_target: float = 0.70
    support_resistance_window_pct: float = 0.10
    migration_windows: tuple[int, ...] = (5, 20, 60)
    divergence_windows: tuple[int, ...] = (20, 60)

    def __post_init__(self) -> None:
        """Reject invalid model priors and geometric parameters."""
        weights = tuple(self.activity_weights.values())
        if any(not 0.0 <= weight <= 1.0 for weight in weights):
            raise ValueError("activity weights must be between 0 and 1")
        if not 0.0 <= self.unknown_activity_weight <= 1.0:
            raise ValueError("unknown_activity_weight must be between 0 and 1")
        if not 0.0 < self.known_coverage_confidence_threshold <= 1.0:
            raise ValueError("known_coverage_confidence_threshold must be in (0, 1]")
        if not 0.0 < self.core_coverage_target <= 1.0:
            raise ValueError("core_coverage_target must be in (0, 1]")
        if not 0.0 < self.support_resistance_window_pct:
            raise ValueError("support_resistance_window_pct must be positive")
        if any(window < 1 for window in self.migration_windows + self.divergence_windows):
            raise ValueError("feature windows must be positive")

@dataclass(frozen=True)
class IndicatorConfig:
    """Stable defaults for indicators; callers may provide their own values."""

    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    kdj_period: int = 9
    kdj_smoothing: int = 3
    position_windows: tuple[int, ...] = (60, 120, 250, 500)

@dataclass(frozen=True)
class MarketConfig:
    """Uncalibrated Phase 3 model priors for market and sector aggregation."""

    position_windows: tuple[int, ...] = (60, 120, 250, 500)
    relative_strength_windows: tuple[int, ...] = (20, 60, 120)
    breadth_ma_windows: tuple[int, ...] = (20, 60, 120, 250)
    strength_weights: Mapping[str, float] = MappingProxyType({
        "structural": 0.35,
        "momentum": 0.25,
        "breadth": 0.20,
        "participation": 0.20,
    })
    sector_strength_weights: Mapping[str, float] = MappingProxyType({
        "position": 0.25,
        "momentum": 0.25,
        "trend": 0.25,
        "relative_strength": 0.25,
    })
    stock_strength_weights: Mapping[str, float] = MappingProxyType({
        "position": 0.25,
        "momentum": 0.25,
        "trend": 0.25,
        "chip": 0.25,
    })
    trend_state_strengths: Mapping[str, float] = MappingProxyType({
        "T0_MAIN_DECLINE": 0.15,
        "T1_DECLINE_STOPPED": 0.35,
        "T2_REVERSAL_CONFIRMED": 0.55,
        "T3_UPTREND": 0.75,
        "T4_ACCELERATION": 0.95,
        "T5_RALLY_EXHAUSTION": 0.40,
        "T6_TREND_BROKEN": 0.05,
    })
    position_neutral_center: float = 0.50
    momentum_scale: float = 1.0
    chip_divergence_scale: float = 0.10
    stock_state_priors: Mapping[str, float] = MappingProxyType({
        "low": 0.50,
        "transition": 0.60,
        "neutral": 0.50,
        "high": 0.50,
        "improving": 0.60,
        "reversal": 0.65,
        "weakening": 0.40,
    })
    chip_state_priors: Mapping[str, float] = MappingProxyType({
        "supportive": 0.60,
        "resistant": 0.40,
        "missing": 0.50,
    })
    cycle_alignment_scores: Mapping[str, float] = MappingProxyType({
        "same": 1.00,
        "progression": 0.90,
        "transition": 0.75,
        "neutral": 0.50,
        "exhaustion": 0.30,
        "breakdown": 0.00,
    })
    cycle_alignment_threshold: float = 0.70
    grade_a_market_states: tuple[str, ...] = ("M3 Bottom Transition", "M5 Bull Trend", "M6 Acceleration")
    grade_a_sector_states: tuple[str, ...] = ("S3 Bottom Transition", "S5 Strong Trend", "S6 Acceleration")
    resonance_weights: Mapping[str, float] = MappingProxyType({
        "market": 0.35,
        "sector": 0.30,
        "stock": 0.35,
    })
    weakest_link_exponent: float = 0.75
    market_gate_floor: float = 0.15
    grade_a_threshold: float = 0.65
    grade_b_threshold: float = 0.52
    grade_c_threshold: float = 0.10

    def __post_init__(self) -> None:
        """Validate configurable priors and windows."""
        if any(window < 1 for window in self.position_windows + self.relative_strength_windows + self.breadth_ma_windows):
            raise ValueError("all market windows must be positive")
        if abs(sum(self.resonance_weights.values()) - 1.0) > 1e-9:
            raise ValueError("resonance weights must sum to 1")
        if any(value < 0.0 for value in self.strength_weights.values()):
            raise ValueError("strength weights must be non-negative")
        for weights in (self.strength_weights, self.sector_strength_weights, self.stock_strength_weights):
            if abs(sum(weights.values()) - 1.0) > 1e-9:
                raise ValueError("strength weights must sum to 1")
        if any(not 0.0 <= value <= 1.0 for value in self.trend_state_strengths.values()):
            raise ValueError("trend state strengths must be in [0, 1]")
        if not 0.0 <= self.position_neutral_center <= 1.0:
            raise ValueError("position_neutral_center must be in [0, 1]")
        if self.momentum_scale <= 0.0 or self.chip_divergence_scale <= 0.0:
            raise ValueError("strength scales must be positive")
        for priors in (self.stock_state_priors, self.chip_state_priors):
            if any(not 0.0 <= value <= 1.0 for value in priors.values()):
                raise ValueError("stock state priors must be in [0, 1]")
        if any(not 0.0 <= value <= 1.0 for value in self.cycle_alignment_scores.values()):
            raise ValueError("cycle alignment scores must be in [0, 1]")
        if not 0.0 <= self.cycle_alignment_threshold <= 1.0:
            raise ValueError("cycle_alignment_threshold must be in [0, 1]")
        if self.weakest_link_exponent <= 0.0:
            raise ValueError("weakest_link_exponent must be positive")
        if not 0.0 <= self.market_gate_floor <= 1.0:
            raise ValueError("market_gate_floor must be in [0, 1]")
        if not 0.0 <= self.grade_c_threshold <= self.grade_b_threshold <= self.grade_a_threshold <= 1.0:
            raise ValueError("grade thresholds must be ordered in [0, 1]")

@dataclass(frozen=True)
class BottomConfig:
    """Phase 4 model priors; no values are historically calibrated yet."""

    position_weights: Mapping[str, float] = MappingProxyType({"60": 0.20, "120": 0.25, "250": 0.25, "500": 0.30})
    chip_weights: Mapping[str, float] = MappingProxyType({"stability": 0.40, "support": 0.35, "pressure": 0.25})
    exhaustion_weights: Mapping[str, float] = MappingProxyType({"volume": 0.25, "price": 0.25, "efficiency": 0.25, "momentum": 0.25})
    momentum_weights: Mapping[str, float] = MappingProxyType({"histogram": 0.25, "slope": 0.20, "divergence": 0.20, "velocity": 0.20, "kdj": 0.15})
    momentum_feature_scales: Mapping[str, float] = MappingProxyType({"histogram": 1.0, "slope": 1.0, "divergence": 1.0, "velocity": 1.0, "kdj": 1.0})
    structural_weights: Mapping[str, float] = MappingProxyType({"position": 0.25, "chip": 0.25, "exhaustion": 0.20, "momentum": 0.10, "resonance": 0.20})
    confirmation_weights: Mapping[str, float] = MappingProxyType({"momentum": 0.60, "trend": 0.40})
    trend_state_priors: Mapping[str, float] = MappingProxyType({"T0_MAIN_DECLINE": 0.10, "T1_DECLINE_STOPPED": 0.55, "T2_REVERSAL_CONFIRMED": 0.80, "T3_UPTREND": 0.70, "T4_ACCELERATION": 0.65, "T5_RALLY_EXHAUSTION": 0.20, "T6_TREND_BROKEN": 0.05})
    exhaustion_priors: Mapping[str, float] = MappingProxyType({"missing": 0.35})
    momentum_priors: Mapping[str, float] = MappingProxyType({"missing": 0.35, "improving": 0.70, "reversal": 0.80, "weakening": 0.20})
    contradiction_threshold: float = 0.65
    risk_r1_factor: float = 0.70
    risk_r2_factor: float = 0.30
    risk_r3_factor: float = 0.05
    l1_threshold: float = 0.40
    l2_threshold: float = 0.50
    l3_threshold: float = 0.50
    l4_threshold: float = 0.75
    resonance_minimum: float = 0.30
    resonance_high: float = 0.65
    rr1_minimum: float = 1.50
    rr2_minimum: float = 2.00
    extreme_volume_ratio: float = 2.0
    price_window_pct: float = 0.10
    chip_distance_scale: float = 0.10
    bearish_momentum_threshold: float = -0.50
    weak_sector_relative_strength: float = -0.10

    def __post_init__(self) -> None:
        """Validate all Phase 4 weights and bounded priors."""
        groups = (self.position_weights, self.chip_weights, self.exhaustion_weights, self.momentum_weights, self.structural_weights, self.confirmation_weights)
        if any(abs(sum(group.values()) - 1.0) > 1e-9 for group in groups):
            raise ValueError("BottomConfig weights must sum to 1")
        values = (self.contradiction_threshold, self.risk_r1_factor, self.risk_r2_factor, self.risk_r3_factor, self.l1_threshold, self.l2_threshold, self.l3_threshold, self.l4_threshold, self.resonance_minimum, self.resonance_high)
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("BottomConfig bounded values must be in [0, 1]")
        if not self.l1_threshold <= self.l2_threshold <= self.l3_threshold <= self.l4_threshold:
            raise ValueError("bottom thresholds must be ordered")
        if self.extreme_volume_ratio <= 0.0 or self.price_window_pct <= 0.0:
            raise ValueError("risk thresholds must be positive")
        if any(value <= 0.0 for value in self.momentum_feature_scales.values()) or self.chip_distance_scale <= 0.0:
            raise ValueError("feature scales must be positive")
        if self.bearish_momentum_threshold >= 0.0 or self.weak_sector_relative_strength >= 0.0:
            raise ValueError("bearish risk thresholds must be negative")
