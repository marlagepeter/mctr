"""Point-in-time risk/reward zones for Bottom Engine output."""

from typing import Optional, Union

import math
from collections.abc import Mapping

import pandas as pd

from mctr.config import BottomConfig
from .models import RiskRewardProfile

def calculate_risk_reward(
    current_price: float,
    chip_profile: object,
    history: Optional[pd.DataFrame] = None,
    config: BottomConfig = BottomConfig(),
) -> RiskRewardProfile:
    """Build resistance zones from current Phase 2 levels and prior history.

    Zones are observable areas, not predicted exact tops. ATR is intentionally not
    introduced because Phase 4 only permits it as a future auxiliary feature.
    """

    if current_price <= 0.0:
        raise ValueError("current_price must be positive")
    support = getattr(chip_profile, "support_density", None)
    resistance = getattr(chip_profile, "resistance_density", None)
    weighted_support = getattr(chip_profile, "weighted_support", None)
    weighted_resistance = getattr(chip_profile, "weighted_resistance", None)
    core_upper = getattr(chip_profile, "core_upper", None)
    overhead = getattr(chip_profile, "peak_price", None)
    highs = history["high"].dropna() if history is not None and "high" in history else pd.Series(dtype=float)
    first_candidates = [value for value in (core_upper, overhead, weighted_resistance) if value is not None and value > current_price]
    first = min(first_candidates) if first_candidates else None
    second = float(highs[highs > (first or current_price)].min()) if not highs.empty and (highs > (first or current_price)).any() else None
    risk = weighted_support if weighted_support is not None and weighted_support < current_price else current_price * (1.0 - config.price_window_pct)
    risk_zone = (float(risk), current_price)

    def zone(value: Optional[float], label: str) -> Optional[tuple[float, float]]:
        return (float(value), float(value) * (1.0 + config.price_window_pct)) if value is not None else None

    first_zone, second_zone = zone(first, "target_1"), zone(second, "target_2")
    extreme_value = float(highs.max()) if not highs.empty else None
    extreme_zone = zone(extreme_value, "extreme") if extreme_value is not None and extreme_value > (second or first or current_price) else None

    def ratio(target: Optional[tuple[float, float]]) -> Optional[float]:
        return (target[0] - current_price) / (current_price - risk) if target is not None and current_price > risk else None

    confidence = "high" if first_zone is not None else "low"
    return RiskRewardProfile(
        entry=current_price, downside_risk_zone=risk_zone, target_zone_1=first_zone,
        target_zone_2=second_zone, extreme_target_zone=extreme_zone, rr1=ratio(first_zone),
        rr2=ratio(second_zone), rr_extreme=ratio(extreme_zone), confidence=confidence,
        explanation="zones use observed chip resistance/core levels and historical highs through as_of_date",
    )
