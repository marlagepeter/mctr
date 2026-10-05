"""Point-in-time market breadth calculations."""

from typing import Optional, Union

import numpy as np
import pandas as pd

from mctr.models.market_data import validate_ohlcv

def calculate_market_breadth(
    closes: pd.DataFrame,
    as_of_date: Optional[object] = None,
) -> pd.DataFrame:
    """Calculate requested breadth counts and moving-average participation.

    ``closes`` contains one stock per column and dates in its index. Each row is
    computed only from observations through that row; invalid current prices are
    excluded from the day's denominator.
    """

    if closes.empty:
        raise ValueError("closes must not be empty")
    frame = closes.copy().sort_index()
    frame.index = pd.to_datetime(frame.index)
    if as_of_date is not None:
        frame = frame.loc[frame.index <= pd.Timestamp(as_of_date)]
    if frame.empty:
        raise ValueError("no breadth data at or before as_of_date")
    result = pd.DataFrame(index=frame.index)
    previous = frame.shift(1)
    result["advance_count"] = ((frame > previous) & frame.notna() & previous.notna()).sum(axis=1)
    result["decline_count"] = ((frame < previous) & frame.notna() & previous.notna()).sum(axis=1)
    result["unchanged_count"] = ((frame == previous) & frame.notna() & previous.notna()).sum(axis=1)
    valid = frame.notna().sum(axis=1)
    result["valid_stock_count"] = valid
    for window in (20, 60, 120, 250):
        above = frame > frame.rolling(window, min_periods=window).mean()
        result[f"above_ma{window}_ratio"] = above.sum(axis=1) / valid.replace(0, np.nan)
    result["new_high_count"] = frame.eq(frame.rolling(250, min_periods=1).max()).sum(axis=1)
    result["new_low_count"] = frame.eq(frame.rolling(250, min_periods=1).min()).sum(axis=1)
    return result

def breadth_profile(breadth: pd.DataFrame, as_of_date: Optional[object] = None):
    """Convert the latest causal breadth row into ``MarketBreadthProfile``."""
    from mctr.market.models import MarketBreadthProfile

    frame = breadth.loc[:pd.Timestamp(as_of_date)] if as_of_date is not None else breadth
    if frame.empty:
        raise ValueError("no breadth row at or before as_of_date")
    row = frame.iloc[-1]
    count = int(row["valid_stock_count"])
    return MarketBreadthProfile(
        as_of_date=frame.index[-1],
        advance_count=int(row["advance_count"]),
        decline_count=int(row["decline_count"]),
        unchanged_count=int(row["unchanged_count"]),
        new_high_count=int(row["new_high_count"]),
        new_low_count=int(row["new_low_count"]),
        above_ma20_ratio=float(row["above_ma20_ratio"]),
        above_ma60_ratio=float(row["above_ma60_ratio"]),
        above_ma120_ratio=float(row["above_ma120_ratio"]),
        above_ma250_ratio=float(row["above_ma250_ratio"]),
        valid_stock_count=count,
        confidence="high" if count > 0 else "low",
    )
