"""Configuration primitives for point-in-time research features."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from mctr.chips.models import ShareholderType


DEFAULT_ACTIVITY_WEIGHTS: Mapping[ShareholderType, float] = MappingProxyType({
    ShareholderType.RETAIL: 0.85,
    ShareholderType.INSTITUTION: 0.45,
    ShareholderType.FUND: 0.55,
    ShareholderType.INSURANCE: 0.25,
    ShareholderType.SOCIAL_SECURITY: 0.20,
    ShareholderType.COMPANY: 0.20,
    ShareholderType.CONTROLLER: 0.10,
    ShareholderType.EXECUTIVE: 0.15,
    ShareholderType.STRATEGIC: 0.10,
    ShareholderType.UNKNOWN: 0.35,
})


@dataclass(frozen=True)
class ChipConfig:
    """Uncalibrated V1 priors and windows for the chip engine."""

    activity_weights: Mapping[ShareholderType, float] = DEFAULT_ACTIVITY_WEIGHTS
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
