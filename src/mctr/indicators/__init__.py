"""Shared indicator namespace reserved for future reusable indicators."""

from typing import Optional

import pandas as pd

from mctr.momentum.indicators import price_volume_features


def calculate_exhaustion_features(frame: pd.DataFrame, config: Optional[object] = None) -> dict[str, float]:
    """Return a compact exhaustion feature dictionary from OHLCV data."""
    if frame.empty:
        return {}
    close = frame["close"]
    volume = frame["volume"]
    pv = price_volume_features(close, volume)
    return {
        "volume": float(pv["volume_exhaustion"].iloc[-1]),
        "price": float(pv["price_velocity"].iloc[-1]),
        "efficiency": float(pv["price_efficiency"].iloc[-1]),
        "momentum": float(pv["volume_velocity"].iloc[-1]),
    }
