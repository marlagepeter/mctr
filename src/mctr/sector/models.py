"""Sector regime data contracts."""

from typing import Mapping, Optional, Union

from dataclasses import dataclass

from mctr.models.states import TrendState

@dataclass(frozen=True)
class SectorRelativeStrengthProfile:
    """Sector returns relative to a market benchmark."""

    returns: Mapping[int, float]

@dataclass(frozen=True)
class SectorRegimeProfile:
    """Point-in-time sector cycle profile."""

    sector_name: str
    as_of_date: object
    position: Mapping[int, float]
    macd: Optional[float]
    macd_histogram: Optional[float]
    macd_histogram_slope: Optional[float]
    kdj_k: Optional[float]
    kdj_d: Optional[float]
    trend_state: Optional[TrendState]
    relative_strength: SectorRelativeStrengthProfile
    position_state: str
    momentum_state: str
    trend_label: str
    cycle_state: str
    position_strength: float
    momentum_strength: float
    trend_strength: float
    relative_strength_strength: float
    sector_strength: float
    confidence: str
    explanation: str
