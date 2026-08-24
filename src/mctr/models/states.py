"""State and score data structures shared by later engines."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Literal


class TrendState(IntEnum):
    T0_MAIN_DECLINE = 0
    T1_DECLINE_STOPPED = 1
    T2_REVERSAL_CONFIRMED = 2
    T3_UPTREND = 3
    T4_ACCELERATION = 4
    T5_RALLY_EXHAUSTION = 5
    T6_TREND_BROKEN = 6


class PositionLevel(IntEnum):
    L1_PRICE_LOW = 1
    L2_STRUCTURE_LOW = 2
    L3_CYCLE_BOTTOM_CANDIDATE = 3
    L4_STRATEGIC_BOTTOM = 4


@dataclass(frozen=True)
class BottomFeatures:
    """Inputs and output contract for the future Bottom Engine."""

    position: float
    chip_structure: float
    exhaustion: float
    momentum: float
    trend: float
    resonance: float
    probability: float | None = None


@dataclass(frozen=True)
class TopFeatures:
    """Inputs and output contract for the future Top Engine."""

    position: float
    chip_dispersion: float
    chip_price_divergence: float
    overhead_resistance: float
    price_efficiency_decline: float
    volume_stagnation: float
    macd_divergence: float
    kdj_heat: float
    trend_exhaustion: float
    market_top: float
    sector_top: float
    probability: float | None = None


@dataclass(frozen=True)
class RiskOverride:
    """Risk veto contract; implementation belongs to the future risk engine."""

    triggered: bool
    reasons: tuple[str, ...] = ()
    max_position: Literal["none", "reduced", "normal"] = "reduced"
