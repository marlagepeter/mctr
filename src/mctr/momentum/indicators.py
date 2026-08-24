"""Momentum and basic price-volume features."""

import numpy as np
import pandas as pd


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Calculate causal MACD, signal, histogram, and histogram slope."""
    if not 1 <= fast < slow or signal < 1:
        raise ValueError("require 1 <= fast < slow and signal >= 1")
    fast_ema = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    slow_ema = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    line = fast_ema - slow_ema
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = line - signal_line
    return pd.DataFrame({"macd": line, "macd_signal": signal_line,
                         "macd_histogram": histogram,
                         "macd_histogram_slope": histogram.diff()})


def kdj(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 9, smoothing: int = 3) -> pd.DataFrame:
    """Calculate causal KDJ values using rolling price range."""
    if period < 2 or smoothing < 1:
        raise ValueError("period must be >= 2 and smoothing must be >= 1")
    lowest = low.rolling(period, min_periods=period).min()
    highest = high.rolling(period, min_periods=period).max()
    span = (highest - lowest).replace(0, np.nan)
    rsv = 100 * (close - lowest) / span
    k = rsv.ewm(com=smoothing - 1, adjust=False, min_periods=smoothing).mean()
    d = k.ewm(com=smoothing - 1, adjust=False, min_periods=smoothing).mean()
    return pd.DataFrame({"kdj_rsv": rsv, "kdj_k": k, "kdj_d": d,
                         "kdj_j": 3 * k - 2 * d})


def price_volume_features(close: pd.Series, volume: pd.Series, window: int = 20) -> pd.DataFrame:
    """Return causal velocity, exhaustion, and efficiency features."""
    if window < 2:
        raise ValueError("window must be at least 2")
    returns = close.pct_change()
    volume_change = volume.pct_change()
    net_move = close.diff(window).abs()
    path = close.diff().abs().rolling(window, min_periods=window).sum()
    efficiency = (net_move / path.where(path != 0)).rename("price_efficiency")
    volume_exhaustion = (volume / volume.rolling(window, min_periods=window).mean()).rename("volume_exhaustion")
    return pd.concat([
        returns.rolling(window, min_periods=window).mean().rename("price_velocity"),
        volume_change.rolling(window, min_periods=window).mean().rename("volume_velocity"),
        volume_exhaustion, efficiency,
    ], axis=1)
