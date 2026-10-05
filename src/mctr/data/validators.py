"""Strict DataFrame validators for historical MCTR inputs."""

from typing import Optional, Union

from collections.abc import Iterable

import numpy as np
import pandas as pd

from .models import DataQualityReport

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
MARKET_BREADTH_COLUMNS = (
    "advance_count", "decline_count", "unchanged_count", "new_high_count", "new_low_count",
    "above_ma20_ratio", "above_ma60_ratio", "above_ma120_ratio", "above_ma250_ratio", "total_turnover",
)

def _date_index(frame: pd.DataFrame, date_column: str = "date") -> pd.DataFrame:
    """Return a copy indexed by validated timestamps without filling data."""

    result = frame.copy()
    if isinstance(result.index, pd.DatetimeIndex):
        result.index = pd.to_datetime(result.index)
    elif date_column in result.columns:
        result[date_column] = pd.to_datetime(result[date_column], errors="raise")
        result = result.set_index(date_column)
    else:
        raise ValueError("data must have a DatetimeIndex or date column")
    return result

def _validate_common(frame: pd.DataFrame, required: Iterable[str], unique_keys: tuple[str, ...] = (), numeric_columns: Optional[Iterable[str]] = None, allow_reorder: bool = False) -> pd.DataFrame:
    """Validate columns, timestamps, order, numeric values and OHLC relations."""
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    result = _date_index(frame)
    if not result.index.is_monotonic_increasing:
        if allow_reorder:
            result = result.sort_index()
        else:
            raise ValueError("dates must be sorted ascending")
    if result.index.has_duplicates and not unique_keys:
        raise ValueError("duplicate dates are not allowed")
    for column in numeric_columns or required:
        if not pd.api.types.is_numeric_dtype(result[column]):
            raise ValueError(f"column {column} must be numeric")
    if set(OHLCV_COLUMNS).issubset(result.columns):
        invalid = (result["low"] > result["high"]) | (result["close"] < result["low"]) | (result["close"] > result["high"])
        invalid |= result["volume"] < 0
        if invalid.any():
            raise ValueError("invalid OHLCV rows or negative volume")
    if unique_keys:
        key_columns = list(unique_keys)
        key_frame = frame.copy()
        if "date" in key_columns and "date" not in key_frame.columns:
            key_frame["date"] = pd.to_datetime(frame.index)
        if any(column not in key_frame.columns for column in key_columns):
            raise ValueError(f"missing uniqueness columns: {key_columns}")
        if key_frame.duplicated(key_columns).any():
            raise ValueError(f"duplicate key: {key_columns}")
    return result

def validate_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate standard date/open/high/low/close/volume input strictly."""
    return _validate_common(frame, OHLCV_COLUMNS)

def validate_stock(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate multi-symbol StockDataFrame with symbol/date uniqueness; allow reordering."""
    if "symbol" not in frame.columns:
        raise ValueError("missing columns: ['symbol']")
    result = _validate_common(frame, OHLCV_COLUMNS + ("symbol",), ("symbol", "date"), OHLCV_COLUMNS, allow_reorder=True)
    return result

def validate_sector(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate multi-sector SectorDataFrame with sector/date uniqueness; allow reordering."""
    if "sector" not in frame.columns:
        raise ValueError("missing columns: ['sector']")
    return _validate_common(frame, OHLCV_COLUMNS + ("sector",), ("sector", "date"), OHLCV_COLUMNS, allow_reorder=True)

def validate_market(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate one market index table using standard OHLCV rules."""
    return validate_ohlcv(frame)

def validate_breadth(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate optional market breadth fields without manufacturing missing values."""
    return _validate_common(frame, MARKET_BREADTH_COLUMNS)

def validate_free_float(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate dated free-float shares; zero and negative values are invalid."""
    required = ("symbol", "free_float_shares")
    result = _validate_common(frame, required, ("symbol", "date"), ("free_float_shares",), allow_reorder=True)
    if (result["free_float_shares"] <= 0).any():
        raise ValueError("free_float_shares must be positive")
    return result

def validate_shareholder(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate effective-dated shareholder activity records; allow reordering by date."""
    required = ("effective_date", "symbol", "shareholder_id", "shares", "holder_type", "activity_weight")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    result = frame.copy()
    result["effective_date"] = pd.to_datetime(result["effective_date"], errors="raise")
    for column in ("shares", "activity_weight"):
        if not pd.api.types.is_numeric_dtype(result[column]):
            raise ValueError(f"column {column} must be numeric")
    if (result["shares"] < 0).any():
        raise ValueError("shares must be non-negative")
    if ((result["activity_weight"] < 0) | (result["activity_weight"] > 1)).any():
        raise ValueError("activity_weight must be between 0 and 1")
    if result.duplicated(["effective_date", "symbol", "shareholder_id"]).any():
        raise ValueError("duplicate shareholder key")
    return result.sort_values("effective_date").reset_index(drop=True)

def quality_report(
    frame: pd.DataFrame,
    required: Iterable[str],
    symbol: Optional[str] = None,
    as_of_date: Optional[object] = None,
    chip_data_available: bool = False,
    market_data_available: bool = False,
    sector_data_available: bool = False,
) -> DataQualityReport:
    """Create a non-mutating quality report for a date-indexed input."""
    missing = tuple(column for column in required if column not in frame.columns)
    indexed = _date_index(frame) if not missing else frame.copy()
    timestamps = indexed.index if isinstance(indexed.index, pd.DatetimeIndex) else pd.DatetimeIndex([])
    duplicate_dates = tuple(pd.DatetimeIndex(timestamps[timestamps.duplicated()]).unique())
    missing_dates: tuple[pd.Timestamp, ...] = ()
    if len(timestamps) > 1:
        expected = pd.date_range(timestamps.min(), timestamps.max(), freq="D")
        missing_dates = tuple(expected.difference(timestamps))
    invalid_rows: list[int] = []
    if set(OHLCV_COLUMNS).issubset(indexed.columns):
        invalid = (indexed["low"] > indexed["high"]) | (indexed["close"] < indexed["low"]) | (indexed["close"] > indexed["high"]) | (indexed["volume"] < 0)
        invalid_rows = list(np.flatnonzero(invalid.to_numpy()))
    future_rows = []
    if as_of_date is not None and isinstance(indexed.index, pd.DatetimeIndex):
        future_rows = list(np.flatnonzero(indexed.index > pd.Timestamp(as_of_date)))
    date_range = (timestamps.min(), timestamps.max()) if len(timestamps) else None
    return DataQualityReport(symbol, date_range, len(frame), missing_dates, duplicate_dates, missing, tuple(invalid_rows), tuple(future_rows), chip_data_available, market_data_available, sector_data_available)
