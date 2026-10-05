"""Momentum indicators."""

from typing import Optional

import pandas as pd

from .indicators import kdj, macd, price_volume_features


def calculate_momentum_features(frame: pd.DataFrame, config: Optional[object] = None) -> dict[str, float]:
    """Build a compact momentum feature dictionary from OHLCV data."""
    if frame.empty:
        return {}
    close = frame["close"]
    volume = frame["volume"]
    result: dict[str, float] = {}
    macd_frame = macd(close)
    result["histogram"] = float(macd_frame["macd_histogram"].iloc[-1])
    result["slope"] = float(macd_frame["macd_histogram_slope"].iloc[-1])
    result["divergence"] = float((close.pct_change().rolling(20, min_periods=20).mean().iloc[-1]))
    if {"high", "low"}.issubset(frame.columns):
        kdj_frame = kdj(frame["high"], frame["low"], close)
        result["kdj"] = float(kdj_frame["kdj_k"].iloc[-1])
    velocity = price_volume_features(close, volume)
    result["velocity"] = float(velocity["price_velocity"].iloc[-1])
    return result


__all__ = ["calculate_momentum_features", "kdj", "macd", "price_volume_features"]
