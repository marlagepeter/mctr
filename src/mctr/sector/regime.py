"""Sector regime calculation using existing Phase 1 indicators."""

from typing import Optional, Union

import numpy as np
import pandas as pd

from mctr.config import MarketConfig
from mctr.models.market_data import validate_ohlcv
from mctr.momentum import kdj, macd, price_volume_features
from mctr.position import position_features
from mctr.trend import classify_trend, trend_features
from mctr.models.states import TrendState
from .models import SectorRegimeProfile, SectorRelativeStrengthProfile
from .relative_strength import calculate_relative_strength

def _last(series: pd.Series) -> Optional[float]:
    """Return the latest non-null scalar or None."""

    values = series.dropna()
    return float(values.iloc[-1]) if not values.empty else None

def _geometric(values: dict[str, float], weights: dict[str, float]) -> float:
    """Aggregate available continuous strengths with a weighted geometric mean."""
    usable = [(key, max(0.0, min(1.0, value))) for key, value in values.items() if np.isfinite(value)]
    total_weight = sum(weights.get(key, 0.0) for key, _ in usable)
    if not usable or total_weight <= 0.0:
        return 0.0
    return float(np.exp(sum(weights.get(key, 0.0) * np.log(max(value, 1e-12)) for key, value in usable) / total_weight))

def calculate_sector_regime(
    sector_name: str,
    sector_frame: pd.DataFrame,
    market_close: pd.Series,
    as_of_date: Optional[object] = None,
    config: MarketConfig = MarketConfig(),
) -> SectorRegimeProfile:
    """Build a causal SectorRegime and its relative strength profile."""
    data = validate_ohlcv(sector_frame)
    if as_of_date is not None:
        cutoff = pd.Timestamp(as_of_date)
        data = data.loc[data.index <= cutoff]
        market_close = market_close.loc[market_close.index <= cutoff]
    if data.empty:
        raise ValueError("sector_frame has no observations at or before as_of_date")
    close = data["close"]
    positions = position_features(close, config.position_windows).iloc[-1].dropna().to_dict()
    macd_values = macd(close)
    kdj_values = kdj(data["high"], data["low"], close)
    trend_values = classify_trend(trend_features(close).join(macd_values["macd_histogram_slope"])).dropna()
    trend_state = int(trend_values.iloc[-1]) if not trend_values.empty else None
    has_breakdown = trend_state == 6
    relative = calculate_relative_strength(close, market_close, config.relative_strength_windows, data.index[-1])
    rel_values = {window: _last(relative[f"relative_strength_{window}d"]) for window in config.relative_strength_windows}
    position_mean = float(np.mean(list(positions.values()))) if positions else np.nan
    momentum = _last(macd_values["macd_histogram_slope"])
    position_state = "low" if np.isfinite(position_mean) and position_mean < 0.3 else "high" if np.isfinite(position_mean) and position_mean > 0.7 else "neutral"
    momentum_state = "improving" if momentum is not None and momentum >= 0 else "weakening" if momentum is not None else "missing"
    trend_label = "decline" if trend_state is not None and trend_state <= 1 else "trend" if trend_state is not None and trend_state >= 3 else "transition"
    reference_window = 20 if 20 in rel_values else min(rel_values)
    rel_reference = rel_values.get(reference_window)
    if has_breakdown:
        cycle = "S8 Breakdown"
    elif trend_label == "decline" and position_state == "low" and momentum_state == "improving":
        cycle = "S3 Bottom Transition"
    elif trend_label == "decline":
        cycle = "S1 Weak"
    elif trend_label == "trend" and position_state == "high" and momentum_state == "improving":
        cycle = "S6 Acceleration"
    elif trend_label == "trend" and rel_reference is not None and rel_reference > 0:
        cycle = "S5 Strong Trend"
    elif trend_label == "trend":
        cycle = "S7 Exhaustion"
    else:
        cycle = "S4 Recovery" if position_state == "low" else "S2 Weakening / Exhaustion"
    position_strength = (
        1.0 - abs(position_mean - config.position_neutral_center) / max(config.position_neutral_center, 1.0 - config.position_neutral_center)
        if np.isfinite(position_mean) else np.nan
    )
    momentum_inputs = price_volume_features(close, data["volume"], window=min(20, max(2, len(data))))
    momentum_components = [
        _last(macd_values["macd_histogram"]), _last(macd_values["macd_histogram_slope"]),
        _last(momentum_inputs["price_velocity"]), _last(momentum_inputs["volume_velocity"]),
        _last(momentum_inputs["volume_exhaustion"]), _last(momentum_inputs["price_efficiency"]),
    ]
    momentum_values = [0.5 + 0.5 * np.tanh(value / config.momentum_scale) for value in momentum_components if value is not None and np.isfinite(value)]
    momentum_strength = float(np.prod(momentum_values) ** (1 / len(momentum_values))) if momentum_values else np.nan
    trend_name = TrendState(trend_state).name if trend_state is not None else None
    trend_strength = config.trend_state_strengths.get(trend_name, np.nan) if trend_name else np.nan
    relative_strength = 0.5 + 0.5 * np.tanh(rel_reference) if rel_reference is not None else np.nan
    component_strengths = {"position": position_strength, "momentum": momentum_strength, "trend": trend_strength, "relative_strength": relative_strength}
    strength = _geometric(component_strengths, dict(config.sector_strength_weights))
    confidence = "high" if sum(np.isfinite(value) for value in component_strengths.values()) == 4 else "medium" if sum(np.isfinite(value) for value in component_strengths.values()) >= 2 else "low"
    return SectorRegimeProfile(
        sector_name=sector_name, as_of_date=data.index[-1], position={int(key.rsplit("_", 1)[-1]): float(value) for key, value in positions.items() if key.startswith("position_")},
        macd=_last(macd_values["macd"]), macd_histogram=_last(macd_values["macd_histogram"]), macd_histogram_slope=momentum,
        kdj_k=_last(kdj_values["kdj_k"]), kdj_d=_last(kdj_values["kdj_d"]), trend_state=trend_state,
        relative_strength=SectorRelativeStrengthProfile(rel_values), position_state=position_state, momentum_state=momentum_state,
        trend_label=trend_label, cycle_state=cycle, position_strength=float(position_strength), momentum_strength=float(momentum_strength),
        trend_strength=float(trend_strength), relative_strength_strength=float(relative_strength), sector_strength=strength, confidence=confidence,
        explanation=f"trend={trend_label}; position={position_state}; momentum={momentum_state}; relative_strength_{reference_window}d={rel_reference}",
    )
