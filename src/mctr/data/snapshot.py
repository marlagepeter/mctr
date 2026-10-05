"""Point-in-time snapshots assembled from validated DataFrames."""

from typing import Optional, Union

from collections.abc import Mapping

import pandas as pd

from .models import HistoricalChipInput, HistoricalDataSnapshot, MarketDataBundle
from .validators import validate_free_float, validate_shareholder

def _dated(frame: Optional[pd.DataFrame], as_of_date: pd.Timestamp) -> Optional[pd.DataFrame]:
    """Filter a date-indexed frame without forward-filling."""

    if frame is None:
        return None
    result = frame.copy()
    if "date" in result.columns:
        result["date"] = pd.to_datetime(result["date"])
        result = result.set_index("date")
    if isinstance(result.index, pd.DatetimeIndex):
        result = result.loc[result.index <= as_of_date]
    return result

def _effective_free_float(frame: Optional[pd.DataFrame], symbol: str, as_of_date: pd.Timestamp) -> Optional[pd.DataFrame]:
    """Keep only historical records through the cutoff for one symbol."""
    if frame is None:
        return None
    validated = validate_free_float(frame)
    filtered = validated.loc[(validated["symbol"] == symbol) & (validated.index <= as_of_date)]
    return filtered.copy()

def _effective_shareholders(frame: Optional[pd.DataFrame], symbol: str, as_of_date: pd.Timestamp) -> Optional[pd.DataFrame]:
    """Keep shareholder records whose effective date is observable at cutoff."""
    if frame is None:
        return None
    validated = validate_shareholder(frame)
    return validated.loc[(validated["symbol"] == symbol) & (validated["effective_date"] <= as_of_date)].copy()

def build_snapshot(
    as_of_date: object,
    symbol: str,
    stock_ohlcv: Optional[pd.DataFrame],
    market_data: Optional[MarketDataBundle] = None,
    sector_data: Optional[pd.DataFrame] = None,
    breadth: Optional[pd.DataFrame] = None,
    free_float: Optional[pd.DataFrame] = None,
    shareholders: Optional[pd.DataFrame] = None,
) -> HistoricalDataSnapshot:
    """Build a snapshot containing only data known at ``as_of_date``.

    Missing market, sector, or chip inputs remain ``None`` and are marked
    unavailable. This function does not synthesize ChipProfile values.
    """
    cutoff = pd.Timestamp(as_of_date)
    stock = _dated(stock_ohlcv, cutoff)
    filtered_market = None
    if market_data is not None:
        filtered_market = MarketDataBundle(
            {name: _dated(frame, cutoff) for name, frame in market_data.indices.items()},
            _dated(market_data.breadth, cutoff),
        )
    filtered_sector = _dated(sector_data, cutoff)
    filtered_breadth = _dated(breadth, cutoff)
    filtered_free_float = _effective_free_float(free_float, symbol, cutoff)
    filtered_shareholders = _effective_shareholders(shareholders, symbol, cutoff)
    chip = HistoricalChipInput(
        filtered_free_float,
        filtered_shareholders,
        filtered_free_float is not None and not filtered_free_float.empty,
    )
    return HistoricalDataSnapshot(
        cutoff,
        symbol,
        stock,
        filtered_market,
        filtered_sector,
        filtered_breadth,
        filtered_free_float,
        filtered_shareholders,
        chip,
        filtered_free_float is not None and not filtered_free_float.empty,
        filtered_market is not None and bool(filtered_market.indices),
        filtered_sector is not None and not filtered_sector.empty,
    )
