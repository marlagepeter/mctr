import numpy as np
import pandas as pd

from mctr.momentum import kdj, macd, price_volume_features


def synthetic_ohlcv() -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    close = pd.Series(np.linspace(10, 20, 40), dtype=float)
    high = close + 1
    low = close - 1
    volume = pd.Series(np.linspace(100, 180, 40), dtype=float)
    return high, low, close, volume


def test_macd_columns_and_causal_change() -> None:
    _, _, close, _ = synthetic_ohlcv()
    result = macd(close, fast=3, slow=5, signal=2)
    assert {"macd", "macd_signal", "macd_histogram", "macd_histogram_slope"} <= set(result)
    changed = close.copy()
    changed.iloc[-1] = 999
    pd.testing.assert_series_equal(result["macd"].iloc[:-1], macd(changed, 3, 5, 2)["macd"].iloc[:-1])


def test_kdj_and_price_volume_features() -> None:
    high, low, close, volume = synthetic_ohlcv()
    kdj_result = kdj(high, low, close, period=5, smoothing=2)
    features = price_volume_features(close, volume, window=5)
    assert {"kdj_k", "kdj_d", "kdj_j"} <= set(kdj_result)
    assert {"price_velocity", "volume_velocity", "volume_exhaustion", "price_efficiency"} <= set(features)
    assert features.iloc[:4].isna().any(axis=None)
