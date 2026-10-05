"""Market regime data contracts."""

from typing import Mapping, Optional, Union

from dataclasses import dataclass

from mctr.models.states import TrendState

@dataclass(frozen=True)
class MarketIndexProfile:
    """Point-in-time indicators for one market index."""

    name: str
    as_of_date: object
    position: Mapping[int, float]
    macd: Optional[float]
    macd_histogram: Optional[float]
    macd_histogram_slope: Optional[float]
    kdj_k: Optional[float]
    kdj_d: Optional[float]
    trend_state: Optional[TrendState]
    confidence: str

@dataclass(frozen=True)
class MarketBreadthProfile:
    """Cross-sectional breadth known at one date."""

    as_of_date: object
    advance_count: int
    decline_count: int
    unchanged_count: int
    new_high_count: int
    new_low_count: int
    above_ma20_ratio: float
    above_ma60_ratio: float
    above_ma120_ratio: float
    above_ma250_ratio: float
    valid_stock_count: int
    confidence: str

@dataclass(frozen=True)
class MarketVolumeProfile:
    """Market participation features."""

    total_market_volume: float
    total_market_amount: Optional[float]
    volume_trend: Optional[float]
    volume_change: Optional[float]
    volume_acceleration: Optional[float]
    confidence: str

@dataclass(frozen=True)
class MarketRegimeProfile:
    """Composite market regime with interpretable component states."""

    as_of_date: object
    index_profiles: Mapping[str, MarketIndexProfile]
    position_state: str
    momentum_state: str
    trend_state: str
    breadth_state: str
    volume_state: str
    structural_strength: float
    momentum_strength: float
    breadth_strength: float
    participation_strength: float
    market_strength: float
    market_cycle_state: str
    confidence: str
    explanation: str
