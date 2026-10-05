"""Causal sector-to-market relative strength features."""

from typing import Optional, Union

import pandas as pd

def calculate_relative_strength(
    sector_close: pd.Series,
    market_close: pd.Series,
    windows: tuple[int, ...] = (20, 60, 120),
    as_of_date: Optional[object] = None,
) -> pd.DataFrame:
    """Calculate sector return minus benchmark return for each requested window."""

    sector = sector_close.sort_index()
    market = market_close.sort_index()
    if as_of_date is not None:
        cutoff = pd.Timestamp(as_of_date)
        sector, market = sector.loc[sector.index <= cutoff], market.loc[market.index <= cutoff]
    joined = pd.concat([sector.rename("sector"), market.rename("market")], axis=1).dropna()
    if joined.empty:
        raise ValueError("sector and market have no common observations")
    result = pd.DataFrame(index=joined.index)
    for window in windows:
        if window < 1:
            raise ValueError("windows must be positive")
        result[f"relative_strength_{window}d"] = joined["sector"].pct_change(window) - joined["market"].pct_change(window)
    return result
