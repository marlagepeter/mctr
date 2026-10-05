"""Market regime calculations and data contracts."""

from typing import Optional, Union

from dataclasses import dataclass

from .breadth import breadth_profile, calculate_market_breadth
from .models import MarketBreadthProfile, MarketIndexProfile, MarketRegimeProfile, MarketVolumeProfile
from .regime import calculate_market_regime, calculate_market_volume

@dataclass(frozen=True)
class MarketRegimeInputs:
    """Backward-compatible input contract retained from Phase 1 scaffolding."""

    index_name: str
    breadth: Optional[float] = None
    new_highs: Optional[int] = None
    new_lows: Optional[int] = None
    above_ma_20: Optional[float] = None
    above_ma_60: Optional[float] = None
    above_ma_120: Optional[float] = None
    above_ma_250: Optional[float] = None
    turnover: Optional[float] = None

__all__ = [
    "MarketBreadthProfile", "MarketIndexProfile", "MarketRegimeInputs", "MarketRegimeProfile",
    "MarketVolumeProfile", "breadth_profile", "calculate_market_breadth",
    "calculate_market_regime", "calculate_market_volume",
]
