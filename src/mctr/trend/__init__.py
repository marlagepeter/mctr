"""Trend structure and state model."""

from typing import Optional

import pandas as pd

from mctr.momentum.indicators import macd
from mctr.models.states import TrendState

from .state import classify_trend, trend_features


def calculate_trend_state(frame: pd.DataFrame, config: Optional[object] = None) -> Optional[str]:
    """Classify the latest trend state from the current close series."""
    if frame.empty:
        return None
    close = frame["close"]
    trend = trend_features(close)
    macd_frame = macd(close)
    features = pd.concat([trend, macd_frame[["macd_histogram_slope"]]], axis=1)
    state = classify_trend(features).iloc[-1]
    if pd.isna(state):
        return None
    if hasattr(state, "name"):
        return state.name
    return TrendState(int(state)).name


__all__ = ["calculate_trend_state", "classify_trend", "trend_features"]
