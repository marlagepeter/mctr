"""Canonical market data contracts."""

from dataclasses import dataclass
from typing import Final

import pandas as pd


@dataclass(frozen=True)
class OHLCVColumns:
    """Column names expected by all point-in-time feature functions."""

    date: str = "date"
    open: str = "open"
    high: str = "high"
    low: str = "low"
    close: str = "close"
    volume: str = "volume"
    amount: str = "amount"


REQUIRED_OHLCV: Final[tuple[str, ...]] = ("open", "high", "low", "close", "volume")


def validate_ohlcv(frame: pd.DataFrame, columns: OHLCVColumns = OHLCVColumns()) -> pd.DataFrame:
    """Return a validated copy with a monotonic datetime index.

    No forward or backward filling is performed: missing observations remain visible.
    """
    required = [getattr(columns, name) for name in REQUIRED_OHLCV]
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise ValueError(f"OHLCV data missing columns: {missing}")
    result = frame.copy()
    if columns.date in result.columns:
        result[columns.date] = pd.to_datetime(result[columns.date], errors="raise")
        result = result.set_index(columns.date)
    if not result.index.is_monotonic_increasing:
        result = result.sort_index()
    if result.index.has_duplicates:
        raise ValueError("OHLCV data must not contain duplicate timestamps")
    return result
