"""Market index and composite regime calculations."""

from typing import Optional, Union

from collections.abc import Mapping

import numpy as np
import pandas as pd

from mctr.config import IndicatorConfig, MarketConfig
from mctr.market.breadth import breadth_profile, calculate_market_breadth
from mctr.market.models import (
    MarketBreadthProfile,
    MarketIndexProfile,
    MarketRegimeProfile,
    MarketVolumeProfile,
)
from mctr.momentum import kdj, macd, price_volume_features
from mctr.position import position_features
from mctr.models.market_data import validate_ohlcv
from mctr.models.states import TrendState
from mctr.trend import classify_trend, trend_features

def _latest(value: pd.Series) -> Optional[float]:
    """Return the latest non-null scalar or None."""

    non_null = value.dropna()
    return float(non_null.iloc[-1]) if not non_null.empty else None

def _index_profile(name: str, frame: pd.DataFrame, config: MarketConfig) -> MarketIndexProfile:
    """Calculate one index profile using existing Phase 1 indicators."""
    data = validate_ohlcv(frame)
    close = data["close"]
    positions = position_features(close, config.position_windows).iloc[-1].dropna().to_dict()
    macd_values = macd(close)
    kdj_values = kdj(data["high"], data["low"], close)
    trend_input = trend_features(close).join(macd_values["macd_histogram_slope"])
    trend_values = classify_trend(trend_input).dropna()
    state = TrendState(int(trend_values.iloc[-1])) if not trend_values.empty else None
    valid_count = len(positions) + sum(value is not None for value in (_latest(macd_values["macd"]), _latest(kdj_values["kdj_k"])))
    confidence = "high" if valid_count >= 4 else "medium" if valid_count >= 2 else "low"
    return MarketIndexProfile(
        name=name,
        as_of_date=data.index[-1],
        position={int(key.rsplit("_", 1)[-1]): float(value) for key, value in positions.items() if key.startswith("position_")},
        macd=_latest(macd_values["macd"]),
        macd_histogram=_latest(macd_values["macd_histogram"]),
        macd_histogram_slope=_latest(macd_values["macd_histogram_slope"]),
        kdj_k=_latest(kdj_values["kdj_k"]),
        kdj_d=_latest(kdj_values["kdj_d"]),
        trend_state=state,
        confidence=confidence,
    )

def calculate_market_volume(frame: pd.DataFrame, as_of_date: Optional[object] = None) -> MarketVolumeProfile:
    """Aggregate market volume/amount and derive existing causal volume features."""
    data = validate_ohlcv(frame)
    if as_of_date is not None:
        data = data.loc[data.index <= pd.Timestamp(as_of_date)]
    if data.empty:
        raise ValueError("no market volume data at or before as_of_date")
    volume = data["volume"]
    amount = data["amount"] if "amount" in data else None
    features = price_volume_features(volume, volume, window=min(20, max(2, len(volume))))
    return MarketVolumeProfile(
        total_market_volume=float(volume.iloc[-1]),
        total_market_amount=float(amount.iloc[-1]) if amount is not None else None,
        volume_trend=_latest(features["price_velocity"]),
        volume_change=_latest(features["volume_velocity"]),
        volume_acceleration=_latest(features["volume_exhaustion"]),
        confidence="high" if len(data) >= 20 else "low",
    )

def _geometric(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Weighted geometric aggregation; missing dimensions are excluded explicitly."""
    usable = [(key, max(0.0, min(1.0, value))) for key, value in values.items() if np.isfinite(value)]
    if not usable:
        return 0.0
    total_weight = sum(weights.get(key, 0.0) for key, _ in usable)
    if total_weight <= 0.0:
        return 0.0
    return float(np.exp(sum(weights.get(key, 0.0) * np.log(max(value, 1e-12)) for key, value in usable) / total_weight))

def calculate_market_regime(
    indices: Mapping[str, pd.DataFrame],
    breadth_closes: Optional[pd.DataFrame] = None,
    volume_frame: Optional[pd.DataFrame] = None,
    as_of_date: Optional[object] = None,
    config: MarketConfig = MarketConfig(),
) -> MarketRegimeProfile:
    """Build a causal MarketRegime from index, breadth, and volume DataFrames."""
    if not indices:
        raise ValueError("indices must not be empty")
    profiles = {
        name: _index_profile(name, frame.loc[:pd.Timestamp(as_of_date)] if as_of_date is not None else frame, config)
        for name, frame in indices.items()
    }
    latest_date = max(profile.as_of_date for profile in profiles.values())
    index_values = list(profiles.values())
    position_values = [value for profile in index_values for value in profile.position.values()]
    structural = float(np.mean(position_values)) if position_values else np.nan
    trend_values = [int(profile.trend_state) for profile in index_values if profile.trend_state is not None]
    trend_mean = float(np.mean(trend_values)) if trend_values else np.nan
    has_breakdown = any(value == int(TrendState.T6_TREND_BROKEN) for value in trend_values)
    momentum_values = [profile.macd_histogram_slope for profile in index_values if profile.macd_histogram_slope is not None]
    momentum = float(np.mean([1.0 if value >= 0 else 0.0 for value in momentum_values])) if momentum_values else np.nan
    position_state = "low" if np.isfinite(structural) and structural < 0.3 else "high" if np.isfinite(structural) and structural > 0.7 else "neutral"
    momentum_state = "improving" if np.isfinite(momentum) and momentum >= 0.5 else "weakening"
    trend_state = "decline" if np.isfinite(trend_mean) and trend_mean < 2 else "trend" if np.isfinite(trend_mean) and trend_mean >= 3 else "transition"
    if breadth_closes is not None:
        breadth = breadth_profile(calculate_market_breadth(breadth_closes, latest_date), latest_date)
        breadth_strength = float(np.nanmean([breadth.above_ma20_ratio, breadth.above_ma60_ratio, breadth.above_ma120_ratio, breadth.above_ma250_ratio]))
        breadth_state = "weak" if breadth_strength < 0.35 else "strong" if breadth_strength > 0.65 else "neutral"
    else:
        breadth = None
        breadth_strength = np.nan
        breadth_state = "missing"
    if volume_frame is not None:
        volume = calculate_market_volume(volume_frame, latest_date)
        participation = 1.0 if (volume.volume_trend is not None and volume.volume_trend >= 0) else 0.0
        volume_state = "expanding" if participation else "contracting"
    else:
        participation = np.nan
        volume_state = "missing"
    structural_strength = max(0.0, min(1.0, structural)) if np.isfinite(structural) else np.nan
    momentum_strength = momentum if np.isfinite(momentum) else np.nan
    market_strength = _geometric({"structural": structural_strength, "momentum": momentum_strength, "breadth": breadth_strength, "participation": participation}, config.strength_weights)
    if has_breakdown:
        cycle = "M8 Breakdown"
    elif trend_state == "decline" and position_state == "low" and momentum_state == "weakening":
        cycle = "M0 Extreme Bear"
    elif trend_state == "decline" and position_state == "low" and momentum_state == "improving":
        cycle = "M3 Bottom Transition"
    elif trend_state == "decline" and position_state == "low":
        cycle = "M2 Decline Exhaustion"
    elif trend_state == "decline":
        cycle = "M1 Bear / Decline"
    elif trend_state == "trend" and position_state == "high" and momentum_state == "improving":
        cycle = "M6 Acceleration"
    elif trend_state == "trend" and momentum_state == "improving":
        cycle = "M5 Bull Trend"
    elif trend_state == "trend":
        cycle = "M7 Bull Exhaustion"
    else:
        cycle = "M4 Recovery" if position_state == "low" else "M2 Decline Exhaustion"
    missing = sum(not np.isfinite(value) for value in (structural_strength, momentum_strength, breadth_strength, participation))
    confidence = "high" if missing == 0 else "medium" if missing <= 1 else "low"
    explanation = f"trend={trend_state}; position={position_state}; momentum={momentum_state}; breadth={breadth_state}; volume={volume_state}"
    return MarketRegimeProfile(
        as_of_date=latest_date,
        index_profiles=profiles,
        position_state=position_state,
        momentum_state=momentum_state,
        trend_state=trend_state,
        breadth_state=breadth_state,
        volume_state=volume_state,
        structural_strength=structural_strength,
        momentum_strength=momentum_strength,
        breadth_strength=breadth_strength,
        participation_strength=participation,
        market_strength=market_strength,
        market_cycle_state=cycle,
        confidence=confidence,
        explanation=explanation,
    )
