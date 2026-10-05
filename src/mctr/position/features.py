"""Historical price-position features."""

from collections.abc import Sequence
from typing import Optional, Union

import pandas as pd


def rolling_price_position(close: pd.Series, window: int) -> pd.Series:
    """Return close location within its trailing high-low range in [0, 1]."""
    if window < 2:
        raise ValueError("window must be at least 2")
    low = close.rolling(window, min_periods=window).min()
    high = close.rolling(window, min_periods=window).max()
    span = high - low
    return ((close - low) / span.where(span != 0)).rename(f"position_{window}")


def price_percentile(close: pd.Series, window: int) -> pd.Series:
    """Return the trailing empirical percentile of today's close.

    The current observation is included because the feature is known at today's close.
    """
    if window < 2:
        raise ValueError("window must be at least 2")
    return close.rolling(window, min_periods=window).rank(pct=True).rename("price_percentile")


def position_features(close: pd.Series, windows: tuple[int, ...] = (60, 120, 250, 500)) -> pd.DataFrame:
    """Build multi-cycle position features without looking ahead."""
    if not windows:
        raise ValueError("windows must not be empty")
    result = pd.concat([rolling_price_position(close, window) for window in windows], axis=1)
    result["price_percentile"] = price_percentile(close, max(windows))
    return result


def calculate_position_percentiles(
    close: Union[pd.Series, pd.DataFrame],
    windows: Optional[Sequence[int]] = None,
    config: Optional[object] = None,
) -> dict[int, float]:
    """Return the latest rolling position percentile for each requested window."""
    if isinstance(close, pd.DataFrame):
        if "close" not in close.columns:
            raise ValueError("close frame must contain a 'close' column")
        close = close["close"]
    if windows is None:
        windows = getattr(config, "position_windows", (60, 120, 250, 500))
    windows = tuple(int(window) for window in windows)
    if not windows:
        raise ValueError("windows must not be empty")
    features = position_features(close, windows)
    percentiles: dict[int, float] = {}
    for window in windows:
        column = features.get(f"position_{window}")
        value = 0.5
        if column is not None and not column.empty:
            value = float(column.iloc[-1])
        percentiles[window] = max(0.0, min(1.0, value))
    return percentiles
